from datetime import datetime, timezone

from app.extensions import db
from app.models import User, UserStatus


def _register_and_activate(client, *, institute_name, institute_email, admin_email, password):
    payload = {
        "institute_name": institute_name,
        "institute_email": institute_email,
        "admin_full_name": "Admin",
        "admin_email": admin_email,
        "password": password,
    }
    client.post("/api/v1/institute/auth/register", json=payload)
    user = db.session.query(User).filter(User.email == admin_email).first()
    user.status = UserStatus.ACTIVE
    user.email_verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return user


def _login(client, email, password):
    return client.post(
        "/api/v1/institute/auth/login", json={"email": email, "password": password}
    )


def _setup_institute(client, suffix: str):
    _register_and_activate(
        client,
        institute_name=f"Institute {suffix}",
        institute_email=f"admissions@{suffix}.example",
        admin_email=f"admin@{suffix}.example",
        password="SuperSecret123",
    )
    _login(client, f"admin@{suffix}.example", "SuperSecret123")


class TestCreateStudent:
    def test_create_student_success(self, client):
        _setup_institute(client, "sa1")
        resp = client.post(
            "/api/v1/institute/students",
            json={
                "name": "Asha Rao",
                "email": "asha@students.example",
                "roll_number": "CS101",
                "department": "CSE",
                "batch": "2027",
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["name"] == "Asha Rao"
        assert data["status"] == "active"

    def test_duplicate_email_rejected(self, client):
        _setup_institute(client, "sa2")
        payload = {"name": "A", "email": "dup@students.example"}
        client.post("/api/v1/institute/students", json=payload)
        resp = client.post("/api/v1/institute/students", json=payload)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "duplicate_student"

    def test_duplicate_roll_number_rejected(self, client):
        _setup_institute(client, "sa3")
        client.post(
            "/api/v1/institute/students",
            json={"name": "A", "email": "a1@students.example", "roll_number": "R1"},
        )
        resp = client.post(
            "/api/v1/institute/students",
            json={"name": "B", "email": "a2@students.example", "roll_number": "R1"},
        )
        assert resp.status_code == 409

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/v1/institute/students", json={"name": "A", "email": "a@x.example"}
        )
        assert resp.status_code == 401

    def test_invalid_email_rejected(self, client):
        _setup_institute(client, "sa4")
        resp = client.post(
            "/api/v1/institute/students", json={"name": "A", "email": "not-an-email"}
        )
        assert resp.status_code == 422


class TestListStudents:
    def test_pagination_and_search(self, client):
        _setup_institute(client, "sl1")
        for i in range(5):
            client.post(
                "/api/v1/institute/students",
                json={
                    "name": f"Student {i}",
                    "email": f"student{i}@sl1.example",
                    "department": "CSE" if i % 2 == 0 else "ECE",
                },
            )

        resp = client.get("/api/v1/institute/students?per_page=2&page=1")
        body = resp.get_json()["data"]
        assert len(body["items"]) == 2
        assert body["pagination"]["total"] == 5

        resp2 = client.get("/api/v1/institute/students?department=ECE")
        body2 = resp2.get_json()["data"]
        assert all(s["department"] == "ECE" for s in body2["items"])

        resp3 = client.get("/api/v1/institute/students?search=Student 3")
        body3 = resp3.get_json()["data"]
        assert len(body3["items"]) == 1
        assert body3["items"][0]["name"] == "Student 3"


class TestUpdateAndDeleteStudent:
    def test_update_student(self, client):
        _setup_institute(client, "su1")
        create_resp = client.post(
            "/api/v1/institute/students",
            json={"name": "Old Name", "email": "u1@su1.example"},
        )
        student_id = create_resp.get_json()["data"]["id"]

        resp = client.patch(
            f"/api/v1/institute/students/{student_id}",
            json={"name": "New Name", "department": "ME"},
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["name"] == "New Name"
        assert data["department"] == "ME"

    def test_delete_student_soft_deletes(self, client):
        _setup_institute(client, "sd1")
        create_resp = client.post(
            "/api/v1/institute/students",
            json={"name": "To Delete", "email": "del@sd1.example"},
        )
        student_id = create_resp.get_json()["data"]["id"]

        del_resp = client.delete(f"/api/v1/institute/students/{student_id}")
        assert del_resp.status_code == 200

        get_resp = client.get(f"/api/v1/institute/students/{student_id}")
        assert get_resp.status_code == 404

        list_resp = client.get("/api/v1/institute/students")
        ids = [s["id"] for s in list_resp.get_json()["data"]["items"]]
        assert student_id not in ids


class TestStudentTenantIsolation:
    def test_institute_b_cannot_read_institute_a_student(self, client):
        _setup_institute(client, "tia")
        create_resp = client.post(
            "/api/v1/institute/students",
            json={"name": "A's Student", "email": "s@tia.example"},
        )
        student_id = create_resp.get_json()["data"]["id"]

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "tib")

        get_resp = client.get(f"/api/v1/institute/students/{student_id}")
        assert get_resp.status_code == 404

        list_resp = client.get("/api/v1/institute/students")
        assert list_resp.get_json()["data"]["pagination"]["total"] == 0

        update_resp = client.patch(
            f"/api/v1/institute/students/{student_id}", json={"name": "Hijacked"}
        )
        assert update_resp.status_code == 404

        delete_resp = client.delete(f"/api/v1/institute/students/{student_id}")
        assert delete_resp.status_code == 404

    def test_same_email_allowed_across_different_institutes(self, client):
        _setup_institute(client, "dupa")
        resp_a = client.post(
            "/api/v1/institute/students",
            json={"name": "Shared Email", "email": "shared@example.com"},
        )
        assert resp_a.status_code == 201

        client.post("/api/v1/institute/auth/logout")
        _setup_institute(client, "dupb")
        resp_b = client.post(
            "/api/v1/institute/students",
            json={"name": "Shared Email B", "email": "shared@example.com"},
        )
        assert resp_b.status_code == 201


class TestCsvImport:
    def _csv_bytes(self, content: str) -> bytes:
        return content.encode("utf-8")

    def test_import_valid_csv(self, client):
        _setup_institute(client, "ci1")
        csv_content = (
            "name,email,roll_number,department,batch\n"
            "Student One,one@ci1.example,R1,CSE,2027\n"
            "Student Two,two@ci1.example,R2,ECE,2027\n"
        )
        from io import BytesIO

        resp = client.post(
            "/api/v1/institute/students/import",
            data={"file": (BytesIO(self._csv_bytes(csv_content)), "students.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["created"] == 2
        assert data["skipped"] == 0

    def test_import_reports_row_errors_without_failing_whole_batch(self, client):
        _setup_institute(client, "ci2")
        csv_content = (
            "name,email,roll_number\n"
            "Good One,good1@ci2.example,R1\n"
            ",missing-name@ci2.example,R2\n"  # missing name
            "Good Two,good2@ci2.example,R3\n"
        )
        from io import BytesIO

        resp = client.post(
            "/api/v1/institute/students/import",
            data={"file": (BytesIO(self._csv_bytes(csv_content)), "students.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()["data"]
        assert data["created"] == 2
        assert data["skipped"] == 1
        assert data["errors"][0]["row"] == 3

    def test_import_rejects_missing_required_columns(self, client):
        _setup_institute(client, "ci3")
        csv_content = "full_name,contact\nA,B\n"
        from io import BytesIO

        resp = client.post(
            "/api/v1/institute/students/import",
            data={"file": (BytesIO(self._csv_bytes(csv_content)), "students.csv")},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "missing_columns"

    def test_import_skips_duplicates_within_file(self, client):
        _setup_institute(client, "ci4")
        csv_content = (
            "name,email\n"
            "First,dup@ci4.example\n"
            "Second,dup@ci4.example\n"
        )
        from io import BytesIO

        resp = client.post(
            "/api/v1/institute/students/import",
            data={"file": (BytesIO(self._csv_bytes(csv_content)), "students.csv")},
            content_type="multipart/form-data",
        )
        data = resp.get_json()["data"]
        assert data["created"] == 1
        assert data["skipped"] == 1

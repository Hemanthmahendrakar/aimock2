"""
Central place to register all blueprints. Keeps app/__init__.py clean
as the module count grows across phases.
"""
from flask import Flask


def register_routes(app: Flask) -> None:
    from app.routes.auth.institute_auth import bp as institute_auth_bp
    from app.routes.institute_dashboard import bp as institute_dashboard_bp
    from app.routes.institutes.profile import bp as institute_profile_bp
    from app.routes.students.students import bp as students_bp
    from app.routes.campaigns.campaigns import bp as campaigns_bp
    from app.routes.interview_templates.interview_templates import bp as interview_templates_bp
    from app.routes.resumes.resumes import bp as resumes_bp
    from app.routes.institute_interviews.institute_interviews import bp as institute_interviews_bp
    from app.routes.interview.interview_session import bp as interview_session_bp
    from app.routes.analytics.analytics import bp as analytics_bp
    from app.routes.health import bp as health_bp
    from app.routes.local_storage import bp as local_storage_bp
    from app.routes.institute_resources import bp as institute_resources_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(local_storage_bp)
    app.register_blueprint(institute_resources_bp)
    app.register_blueprint(institute_auth_bp)
    app.register_blueprint(institute_dashboard_bp)
    app.register_blueprint(institute_profile_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(interview_templates_bp)
    app.register_blueprint(resumes_bp)
    app.register_blueprint(institute_interviews_bp)
    app.register_blueprint(interview_session_bp)
    app.register_blueprint(analytics_bp)

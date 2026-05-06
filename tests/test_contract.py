from memory_service.main import create_app


def test_app_is_created_with_health_route():
    app = create_app()

    routes = {route.path for route in app.routes}

    assert app.title == "Memory Service"
    assert "/health" in routes

def __getattr__(name: str):
    if name == "router":
        from app.ai.routes import router

        return router
    raise AttributeError(name)


__all__ = ["router"]

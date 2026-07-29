from ninja import NinjaAPI
from api.auth import router as auth_router
from api.endpoints import router as endpoints_router

api = NinjaAPI(
    title="Scraper Bot API",
    version="1.0.0",
    description="API do Bot de Raspagem Agêntico",
    auth=None,
)

api.add_router('/', auth_router)
api.add_router('/', endpoints_router)

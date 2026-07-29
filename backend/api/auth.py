from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django_ratelimit.decorators import ratelimit
from ninja import Router, Schema

router = Router()


class LoginInput(Schema):
    username: str
    password: str


class UserSchema(Schema):
    id: int
    username: str


class AuthResponse(Schema):
    success: bool
    user: UserSchema | None = None
    error: str | None = None


@router.post('/auth/login/', response=AuthResponse, auth=None)
@ratelimit(key='ip', rate='10/m', method='POST', block=True)
def login_view(request, payload: LoginInput):
    user = authenticate(
        request,
        username=payload.username,
        password=payload.password
    )
    if user is not None:
        login(request, user)
        return AuthResponse(
            success=True,
            user=UserSchema(id=user.id, username=user.username)
        )
    return AuthResponse(
        success=False,
        error='Credenciais inválidas'
    )


@router.post('/auth/logout/', response=AuthResponse)
def logout_view(request):
    logout(request)
    return AuthResponse(success=True)


@router.get('/auth/me/', response=AuthResponse)
def me_view(request):
    if not request.user.is_authenticated:
        return AuthResponse(success=False, error='Não autenticado')
    return AuthResponse(
        success=True,
        user=UserSchema(id=request.user.id, username=request.user.username)
    )



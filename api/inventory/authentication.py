from rest_framework_simplejwt.authentication import JWTAuthentication

class AccessJWTAuthentication(JWTAuthentication):
    def get_header(self, request):
        token = request.COOKIES.get('access')
        request.META['HTTP_AUTHORIZATION'] = '{header_type} {access_token}'.format(header_type="Bearer", access_token=token)
        return super().get_header(request)

class RefreshJWTAuthentication(JWTAuthentication):
    def get_header(self, request):
        refresh = request.COOKIES.get('refresh')
        request.META['HTTP_REFRESH_TOKEN'] = refresh
        return super().get_header(request)

from api.inventory.exception import BusinessException
from django.conf import settings
from django.db.models import F, Value, Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Product, Purchase, Sales
from .serializers import InventorySerializer, ProductSerializer, PurchaseSerializer, SaleSerializer
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from api.inventory.authentication import RefreshJWTAuthentication

class ProductView(APIView):

    # 商品操作に関する関数で共通で使用する商品取得関数
    def get_object(self, pk):
        try:
            return Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            raise NotFound

    """
    商品操作に関する関数
    """
    def get(self, request, id=None, format=None):
        """
        商品の一覧を取得する
        """
        if id is None :
            queryset = Product.objects.all()
            serializer = ProductSerializer(queryset, many=True)
        else: 
            product = self.get_object(id)
            serializer = ProductSerializer(product)
        return Response(serializer.data, status.HTTP_200_OK)

    def post(self, request, format=None):
        """
        商品を登録する
        """
        serializer = ProductSerializer(data=request.data)
        # validationを通らなかった場合、例外を投げる
        serializer.is_valid(raise_exception=True)
        # 検証したデータを永続化する
        serializer.save()
        return Response(serializer.data, status.HTTP_201_CREATED)

    def put(self, request, id, format=None):
        """
        商品を更新する
        """
        product = self.get_object(id)
        serializer = ProductSerializer(instance=product, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status.HTTP_200_OK)

    def delete(self, request, id, format=None):
        """
        商品を削除する
        """
        product = self.get_object(id)
        product.delete()
        return Response(status = status.HTTP_200_OK)

class ProductModelViewSet(ModelViewSet):
    """
    商品操作に関する関数（ModelViewSet）
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer

class PurchaseView(APIView):
    def post(self, request, format=None):
        """
        仕入情報を登録する
        """
        serializer = PurchaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status.HTTP_201_CREATED)

class SalesView(APIView):
    def post(self, request, format=None):
        """
        売上情報を登録する
        """
        serializer = SaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # 在庫が売る分の数量を超えないかチェック
        purchase = Purchase.objects.filter(product_id=request.data['product']).aggregate(quantity_sum=Coalesce(Sum('quantity'), 0)) # 在庫テーブルのレコードを取得
        sales = Sales.objects.filter(product_id=request.data['product']).aggregate(quantity_sum=Coalesce(Sum('quantity'), 0)) # 卸しテーブルのレコードを取得

        # 在庫が売る分の数量を超えている場合はエラーレスポンスを返す
        if purchase['quantity_sum'] < (sales['quantity_sum'] + int(request.data['quantity'])):
            raise BusinessException('在庫数量を超過することはできません')

        serializer.save()
        return Response(serializer.data, status.HTTP_201_CREATED)
class InventoryView(APIView):
    # 仕入れ・売上情報を取得する
    def get(self, request, id=None, format=None):
        if id is None :
            # 件数が多くなるので商品IDは必ず指定する
            return Response(serializer.data, status.HTTP_400_BAD_REQUEST)
        else:
            # UNIONするために、それぞれフィールド名を再定義している
            purchase = Purchase.objects.filter(product_id=id).prefetch_related('product').values("id", "quantity", type=Value('1'), date=F('purchase_date'),unit=F('product__price'))
            sales = Sales.objects.filter(product_id=id).prefetch_related('product').values("id", "quantity", type=Value('2'), date=F('sales_date'),unit=F('product__price'))
            queryset = purchase.union(sales).order_by(F("date"))
            serializer = InventorySerializer(queryset, many=True)
            return Response(serializer.data, status.HTTP_200_OK)

class LoginView(APIView):
    """ユーザーのログイン処理
    Args:
    APIView (class): rest_framework.viewsのAPIViewを受け取る
    """
    # 認証クラスの指定
    # リクエストヘッダーにtokenを差し込むといったカスタム動作をしないので素の認証クラスを使用する
    authentication_classes = [JWTAuthentication]
    # アクセス許可の指定
    permission_classes = []

    def post(self, request):
        serializer = TokenObtainPairSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access = serializer.validated_data.get("access", None)
        refresh = serializer.validated_data.get("refresh", None)
        if access:
            response = Response(status=status.HTTP_200_OK)
            max_age = settings.COOKIE_TIME
            response.set_cookie('access', access, httponly=True, max_age=max_age)
            response.set_cookie('refresh', refresh, httponly=True, max_age=max_age)
            return response
        return Response({'errMsg': 'ユーザーの認証に失敗しました'}, status=status.HTTP_401_UNAUTHORIZED)

class RetryView(APIView):
    authentication_classes = [RefreshJWTAuthentication]
    permission_classes = []

    def post(self, request):
        request.data['refresh'] = request.META.get('HTTP_REFRESH_TOKEN')
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access = serializer.validated_data.get("access", None)
        refresh = serializer.validated_data.get("refresh", None)
        if access:
            response = Response(status=status.HTTP_200_OK)
            max_age = settings.COOKIE_TIME
            response.set_cookie('access', access, httponly=True, max_age=max_age)
            response.set_cookie('refresh', refresh, httponly=True, max_age=max_age)
            return response
        return Response({'errMsg': 'ユーザーの認証に失敗しました'}, status=status.HTTP_401_UNAUTHORIZED)

class LogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args):
        response = Response(status=status.HTTP_200_OK)
        response.delete_cookie('access')
        response.delete_cookie('refresh')
        return response
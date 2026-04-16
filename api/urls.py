from django.urls import path

from api import catalog, checkout, views

urlpatterns = [
    path("products/sync/", views.ProductSyncView.as_view(), name="api-products-sync"),
    path("categories/sync/", views.CategorySyncView.as_view(), name="api-categories-sync"),
    path("customers/sync/", views.CustomerSyncView.as_view(), name="api-customers-sync"),
    path(
        "customers/pull-from-onec/",
        views.CustomerPullFromOneCView.as_view(),
        name="api-customers-pull-from-onec",
    ),
    path(
        "onec/sync-full/",
        views.FullOneCSyncView.as_view(),
        name="api-onec-sync-full",
    ),
    path("orders/export/", views.OrderExportView.as_view(), name="api-orders-export"),
    path("orders/status/", views.OrderStatusView.as_view(), name="api-orders-status"),
    path("payments/webhook/", views.PaymentWebhookView.as_view(), name="api-payments-webhook"),
    path("catalog/categories/", catalog.CategoryListView.as_view(), name="api-catalog-categories"),
    path("catalog/products/", catalog.ProductListView.as_view(), name="api-catalog-products"),
    path("catalog/products/<str:pk>/", catalog.ProductDetailView.as_view(), name="api-catalog-product-detail"),
    path("checkout/orders/", checkout.CheckoutOrderView.as_view(), name="api-checkout-order"),
]

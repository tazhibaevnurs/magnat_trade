from django.urls import path
from . import manager_views, views
from .api import auth
from django.contrib.auth.views import LogoutView


urlpatterns = [
    path('', views.landing, name='landing'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('catalog/product/<path:product_id>/', views.catalog_pdp, name='catalog_pdp'),
    path('product/<slug:slug>/', views.pdp, name='pdp'),
    path('sign-in/', views.sign_in, name='sign-in'),
    path('sign-up/', views.sign_up, name='sign-up'),
    path('shop/', views.shop, name='shop'),
    path('shop/grid/', views.shop_grid, name='shop_grid'),
    path('api/shop/products/', views.shop_products_api, name='shop-products-api'),
    path('api/shop/categories-search/', views.categories_search_api, name='categories-search-api'),
    path('cart/', views.cart, name='cart'),
    path('about-us/', views.about_us, name='about-us'),
    path('contact-us/', views.contact_us, name='contact-us'),
    path('profile/', views.user_profile, name='profile'),
    path('profile/manager/', manager_views.manager_dashboard, name='manager_dashboard'),
    path('profile/manager/products-panel/', manager_views.manager_products_panel, name='manager_products_panel'),
    path('profile/manager/categories-panel/', manager_views.manager_categories_panel, name='manager_categories_panel'),
    path('profile/manager/users-panel/', manager_views.manager_users_panel, name='manager_users_panel'),
    path(
        'profile/manager/wholesale/<int:pk>/approve/',
        manager_views.manager_wholesale_approve,
        name='manager_wholesale_approve',
    ),
    path(
        'profile/manager/wholesale/<int:pk>/reject/',
        manager_views.manager_wholesale_reject,
        name='manager_wholesale_reject',
    ),
    path(
        'profile/manager/category/<path:pk>/delete/',
        manager_views.manager_category_delete,
        name='manager_category_delete',
    ),
    path(
        'profile/manager/user/<int:pk>/delete/',
        manager_views.manager_user_delete,
        name='manager_user_delete',
    ),
    path('profile/address/add/', views.add_address, name='add_address'),
    path('profile/address/edit/<int:address_id>/', views.edit_address, name='edit_address'),
    path('profile/address/delete/<int:address_id>/', views.delete_address, name='delete_address'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/delete-account/', views.delete_account, name='delete_account'),
    path('api/login/', auth.handle_account_authorization, name='api-login'),
    path('api/register/', auth.handle_account_registration, name='api-register'),
    path('api/cart-count/', views.cart_count_api, name='cart-count-api'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/item/<int:item_id>/update/', views.update_cart_item, name='update_cart_item'),
    path('cart/item/<int:item_id>/remove/', views.remove_cart_item, name='remove_cart_item'),
    path('checkout/', views.checkout, name='checkout'),
    path('feedback/', views.feedback, name='feedback'),
    path('feedback/success/', views.feedback_success, name='feedback_success'),
    path('orders/', views.orders, name='orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
]

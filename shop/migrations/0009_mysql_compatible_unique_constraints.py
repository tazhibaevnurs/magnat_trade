from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shop", "0008_alter_wishlistitem_options"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="cartitem",
                    name="uniq_cartitem_shop_product",
                ),
                migrations.RemoveConstraint(
                    model_name="cartitem",
                    name="uniq_cartitem_catalog_product",
                ),
                migrations.RemoveConstraint(
                    model_name="wishlistitem",
                    name="uniq_wishlist_user_catalog_product",
                ),
                migrations.RemoveConstraint(
                    model_name="wishlistitem",
                    name="uniq_wishlist_user_shop_product",
                ),
                migrations.RemoveConstraint(
                    model_name="promotionitem",
                    name="shop_promotionitem_uniq_catalog_product",
                ),
                migrations.RemoveConstraint(
                    model_name="promotionitem",
                    name="shop_promotionitem_uniq_shop_product",
                ),
                migrations.RemoveConstraint(
                    model_name="newarrivalitem",
                    name="shop_newarrivalitem_uniq_catalog_product",
                ),
                migrations.RemoveConstraint(
                    model_name="newarrivalitem",
                    name="shop_newarrivalitem_uniq_shop_product",
                ),
                migrations.AddConstraint(
                    model_name="cartitem",
                    constraint=models.UniqueConstraint(
                        fields=("cart", "product"),
                        name="uniq_cartitem_shop_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="cartitem",
                    constraint=models.UniqueConstraint(
                        fields=("cart", "catalog_product"),
                        name="uniq_cartitem_catalog_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="wishlistitem",
                    constraint=models.UniqueConstraint(
                        fields=("user", "catalog_product"),
                        name="uniq_wishlist_user_catalog_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="wishlistitem",
                    constraint=models.UniqueConstraint(
                        fields=("user", "shop_product"),
                        name="uniq_wishlist_user_shop_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="promotionitem",
                    constraint=models.UniqueConstraint(
                        fields=("catalog_product",),
                        name="shop_promotionitem_uniq_catalog_product_key",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="promotionitem",
                    constraint=models.UniqueConstraint(
                        fields=("shop_product",),
                        name="shop_promotionitem_uniq_shop_product_key",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="newarrivalitem",
                    constraint=models.UniqueConstraint(
                        fields=("catalog_product",),
                        name="shop_newarrivalitem_uniq_catalog_product_key",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="newarrivalitem",
                    constraint=models.UniqueConstraint(
                        fields=("shop_product",),
                        name="shop_newarrivalitem_uniq_shop_product_key",
                    ),
                ),
            ],
            database_operations=[
                migrations.AddConstraint(
                    model_name="cartitem",
                    constraint=models.UniqueConstraint(
                        fields=("cart", "product"),
                        name="uniq_cartitem_shop_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="cartitem",
                    constraint=models.UniqueConstraint(
                        fields=("cart", "catalog_product"),
                        name="uniq_cartitem_catalog_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="wishlistitem",
                    constraint=models.UniqueConstraint(
                        fields=("user", "catalog_product"),
                        name="uniq_wishlist_user_catalog_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="wishlistitem",
                    constraint=models.UniqueConstraint(
                        fields=("user", "shop_product"),
                        name="uniq_wishlist_user_shop_product_pair",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="promotionitem",
                    constraint=models.UniqueConstraint(
                        fields=("catalog_product",),
                        name="shop_promotionitem_uniq_catalog_product_key",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="promotionitem",
                    constraint=models.UniqueConstraint(
                        fields=("shop_product",),
                        name="shop_promotionitem_uniq_shop_product_key",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="newarrivalitem",
                    constraint=models.UniqueConstraint(
                        fields=("catalog_product",),
                        name="shop_newarrivalitem_uniq_catalog_product_key",
                    ),
                ),
                migrations.AddConstraint(
                    model_name="newarrivalitem",
                    constraint=models.UniqueConstraint(
                        fields=("shop_product",),
                        name="shop_newarrivalitem_uniq_shop_product_key",
                    ),
                ),
            ],
        )
    ]

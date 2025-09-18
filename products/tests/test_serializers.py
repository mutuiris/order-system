"""
Unit tests for products app serializers
Test serialization, validation and custom methods for category and product serializers
"""
from decimal import Decimal

import pytest

from products.api.serializers import (CategoryAveragePriceSerializer,
                                      CategorySerializer,
                                      CategoryTreeSerializer,
                                      ProductDetailSerializer,
                                      ProductListSerializer)
from products.models import Category, Product


@pytest.mark.django_db
def test_category_serializer_core_fields_and_product_count():
    parent = Category.objects.create(name="Electronics", slug="electronics")
    child = Category.objects.create(name="Smartphones", slug="smartphones", parent=parent)

    # Active and inactive products
    Product.objects.create(name="Active Phone", sku="A-1", price=Decimal("299.99"), category=child, stock_quantity=5)
    Product.objects.create(name="Inactive Phone", sku="I-1", price=Decimal("199.99"), category=child, stock_quantity=3, is_active=False)

    data_root = CategorySerializer(parent).data
    assert data_root["name"] == "Electronics"
    assert data_root["level"] == 0

    data_child = CategorySerializer(child).data
    assert data_child["name"] == "Smartphones"
    assert data_child["parent"] == parent.pk
    assert data_child["parent_name"] == "Electronics"
    assert data_child["level"] == 1
    assert data_child["full_path"] == "Electronics > Smartphones"
    assert data_child["product_count"] == 1


@pytest.mark.django_db
def test_category_tree_serializer_structure():
    root = Category.objects.create(name="Root", slug="root")
    c1 = Category.objects.create(name="Child 1", slug="child-1", parent=root)
    Category.objects.create(name="Grandchild", slug="grandchild", parent=c1)

    data = CategoryTreeSerializer(root).data
    assert data["name"] == "Root" and data["level"] == 0
    assert len(data["children"]) == 2
    child1 = next(c for c in data["children"] if c["name"] == "Child 1")
    assert child1["level"] == 1
    assert len(child1["children"]) == 1
    assert child1["children"][0]["name"] == "Grandchild"
    assert child1["children"][0]["level"] == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "is_active,stock,expected",
    [
        (True, 10, True),
        (False, 10, False),
        (True, 0, False),
        (False, 0, False),
    ],
)
def test_product_list_serializer_availability_and_category_path(is_active, stock, expected):
    parent = Category.objects.create(name="Parent Category", slug="parent")
    child = Category.objects.create(name="Test Category", slug="test", parent=parent)
    p = Product.objects.create(
        name="Test Product",
        sku="TEST-001",
        price=Decimal("99.99"),
        category=child,
        stock_quantity=stock,
        is_active=is_active,
    )

    data = ProductListSerializer(p).data
    assert data["name"] == "Test Product"
    assert data["category_path"] == "Parent Category > Test Category"
    assert data["is_available"] is expected


@pytest.mark.django_db
def test_product_detail_serializer_related_products_filtering():
    cat = Category.objects.create(name="Cat", slug="cat")
    main = Product.objects.create(
        name="Main", sku="MAIN-1", price=Decimal("50.00"), category=cat, stock_quantity=5
    )
    rel1 = Product.objects.create(
        name="Rel 1", sku="REL-1", price=Decimal("60.00"), category=cat, stock_quantity=5
    )
    Product.objects.create(
        name="Rel 2", sku="REL-2", price=Decimal("70.00"), category=cat, stock_quantity=5, is_active=False
    )

    data = ProductDetailSerializer(main).data
    assert data["name"] == "Main"
    assert data["category"]["name"] == "Cat"
    names = [p["name"] for p in data["related_products"]]
    assert names == ["Rel 1"]
    assert "Main" not in names


def test_category_average_price_serializer_output():
    payload = {
        "category_id": 1,
        "category_name": "Test Category",
        "average_price": Decimal("150.00"),
        "product_count": 3,
        "includes_subcategories": True,
        "min_price": Decimal("100.00"),
        "max_price": Decimal("200.00"),
        "ignored": "x",
    }

    data = CategoryAveragePriceSerializer(payload).data
    assert data["category_id"] == 1
    assert data["category_name"] == "Test Category"
    assert data["average_price"] == "150.00"
    assert data["product_count"] == 3
    assert data["includes_subcategories"] is True
    assert data["price_range"]["min_price"] == "100.00"
    assert data["price_range"]["max_price"] == "200.00"
    assert "ignored" not in data

"""
Unit tests for Product and Category models
Tests hierarchy, business logic, and model relationships
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from products.models import Category, Product


class CategoryModelTest(TestCase):
    """Test Category model business logic"""

    def setUp(self):
        """Set up test data"""
        self.root_category = Category.objects.create(
            name="Electronics", slug="electronics"
        )

    def test_category_hierarchy_creation(self):
        """Test creating category hierarchy with automatic level calculation"""
        child = Category.objects.create(
            name="Smartphones", slug="smartphones", parent=self.root_category
        )

        grandchild = Category.objects.create(name="iPhone", slug="iphone", parent=child)

        # Test hierarchy levels are auto calculated
        self.assertEqual(self.root_category.level, 0)
        self.assertEqual(child.level, 1)
        self.assertEqual(grandchild.level, 2)

    def test_category_full_path_generation(self):
        """Test full path generation for category hierarchy"""
        child = Category.objects.create(
            name="Smartphones", slug="smartphones", parent=self.root_category
        )

        grandchild = Category.objects.create(name="iPhone", slug="iphone", parent=child)

        self.assertEqual(self.root_category.get_full_path(), "Electronics")
        self.assertEqual(child.get_full_path(), "Electronics > Smartphones")
        self.assertEqual(
            grandchild.get_full_path(), "Electronics > Smartphones > iPhone"
        )

    def test_category_descendants_collection(self):
        """Test getting all descendant categories"""
        child1 = Category.objects.create(
            name="Child1", slug="child1", parent=self.root_category
        )

        child2 = Category.objects.create(
            name="Child2", slug="child2", parent=self.root_category
        )

        grandchild = Category.objects.create(
            name="GrandChild", slug="grandchild", parent=child1
        )

        descendants = self.root_category.get_descendants()

        self.assertEqual(len(descendants), 3)
        self.assertIn(child1, descendants)
        self.assertIn(child2, descendants)
        self.assertIn(grandchild, descendants)

    def test_category_unique_constraints(self):
        """Test category uniqueness constraints"""
        Category.objects.create(name="First", slug="duplicate")

        with self.assertRaises(IntegrityError):
            Category.objects.create(name="Second", slug="duplicate")

        Category.objects.create(
            name="Duplicate", slug="duplicate1", parent=self.root_category
        )

        with self.assertRaises(IntegrityError):
            Category.objects.create(
                name="Duplicate", slug="duplicate2", parent=self.root_category
            )


class ProductModelTest(TestCase):
    """Test Product model business logic"""

    def setUp(self):
        """Set up test data"""
        self.category = Category.objects.create(
            name="Test Category", slug="test-category"
        )

    def test_product_stock_management(self):
        """Test product stock reduction functionality"""
        product = Product.objects.create(
            name="Stock Test Product",
            sku="STOCK-TEST-001",
            price=Decimal("99.99"),
            category=self.category,
            stock_quantity=10,
        )

        # Test successful stock reduction
        result = product.reduce_stock(3)
        self.assertTrue(result)
        self.assertEqual(product.stock_quantity, 7)

        # Test reducing more than available stock
        result = product.reduce_stock(10)
        self.assertFalse(result)
        self.assertEqual(product.stock_quantity, 7)

    def test_product_availability_logic(self):
        """Test product availability business logic"""
        product = Product.objects.create(
            name="Availability Test",
            sku="AVAIL-001",
            price=Decimal("99.99"),
            category=self.category,
            stock_quantity=5,
            is_active=True,
        )

        # Product with stock and active should be available
        self.assertTrue(product.is_in_stock)

        # Product with no stock should not be available
        product.stock_quantity = 0
        product.save()
        self.assertFalse(product.is_in_stock)

        # Product with stock but inactive should not be available
        product.stock_quantity = 5
        product.is_active = False
        product.save()
        self.assertFalse(product.is_in_stock)

    def test_product_price_validation(self):
        """Test product price validation rules"""
        # Valid minimum price
        product = Product.objects.create(
            name="Valid Product",
            sku="VALID-001",
            price=Decimal("0.01"),
            category=self.category,
        )
        self.assertEqual(product.price, Decimal("0.01"))

        with self.assertRaises(ValidationError):
            product = Product(
                name="Invalid Product",
                sku="INVALID-001",
                price=Decimal("0.00"),
                category=self.category,
            )
            product.full_clean()

    def test_product_sku_uniqueness(self):
        """Test product SKU uniqueness constraint"""
        Product.objects.create(
            name="First Product",
            sku="DUPLICATE-SKU",
            price=Decimal("99.99"),
            category=self.category,
        )

        with self.assertRaises(IntegrityError):
            Product.objects.create(
                name="Second Product",
                sku="DUPLICATE-SKU",
                price=Decimal("199.99"),
                category=self.category,
            )

    def test_product_category_relationship_protection(self):
        """Test that categories with products cannot be deleted"""
        product = Product.objects.create(
            name="Protected Product",
            sku="PROT-001",
            price=Decimal("99.99"),
            category=self.category,
        )

        with self.assertRaises(Exception):
            self.category.delete()

        self.assertTrue(Product.objects.filter(pk=product.pk).exists())

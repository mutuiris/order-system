"""
Specialized tests for Category hierarchy functionality
Tests complex hierarchy operations, edge cases, and performance
"""

from typing import Any, Dict, List

import pytest
from django.db import transaction
from django.test import TestCase, TransactionTestCase

from products.models import Category, Product
from products.tests.factories import (CategoryHierarchyBuilder,
                                      create_category_hierarchy)


class CategoryHierarchyTest(TestCase):
    """Test category hierarchy functionality"""

    def setUp(self) -> None:
        """Set up complex hierarchy for testing"""
        # Create a 4 level hierarchy
        self.electronics = Category.objects.create(
            name="Electronics", slug="electronics"
        )
        self.computers = Category.objects.create(
            name="Computers", slug="computers", parent=self.electronics
        )
        self.laptops = Category.objects.create(
            name="Laptops", slug="laptops", parent=self.computers
        )
        self.gaming_laptops = Category.objects.create(
            name="Gaming Laptops", slug="gaming-laptops", parent=self.laptops
        )

        # Create products in various levels
        self.laptop_product = Product.objects.create(
            name="MacBook Pro",
            sku="MBP-001",
            price="1999.00",
            category=self.laptops,
            stock_quantity=5,
        )
        self.gaming_product = Product.objects.create(
            name="Gaming Beast",
            sku="GAME-001",
            price="2499.00",
            category=self.gaming_laptops,
            stock_quantity=3,
        )

    def test_deep_hierarchy_creation(self) -> None:
        """Test creating deep category hierarchy"""
        self.assertEqual(self.electronics.level, 0)
        self.assertEqual(self.computers.level, 1)
        self.assertEqual(self.laptops.level, 2)
        self.assertEqual(self.gaming_laptops.level, 3)

        level1 = Category.objects.create(
            name="Level 1", slug="level-1", parent=self.gaming_laptops
        )
        level2 = Category.objects.create(name="Level 2", slug="level-2", parent=level1)
        self.assertEqual(level1.level, 4)
        self.assertEqual(level2.level, 5)

    def test_hierarchy_path_generation(self) -> None:
        """Test full path generation for deep hierarchy"""
        self.assertEqual(self.electronics.get_full_path(), "Electronics")
        self.assertEqual(self.computers.get_full_path(), "Electronics > Computers")
        self.assertEqual(
            self.laptops.get_full_path(), "Electronics > Computers > Laptops"
        )
        self.assertEqual(
            self.gaming_laptops.get_full_path(),
            "Electronics > Computers > Laptops > Gaming Laptops",
        )
        self.assertEqual(
            self.gaming_laptops.get_display_name(),
            "Electronics > Computers > Laptops > Gaming Laptops",
        )

    def test_descendants_collection(self) -> None:
        """Test collecting all descendant categories"""
        descendants = self.electronics.get_descendants()

        self.assertEqual(len(descendants), 3)
        self.assertIn(self.computers, descendants)
        self.assertIn(self.laptops, descendants)
        self.assertIn(self.gaming_laptops, descendants)

        desktop = Category.objects.create(
            name="Desktops", slug="desktops", parent=self.computers, sort_order=1
        )
        workstation = Category.objects.create(
            name="Workstations", slug="workstations", parent=desktop
        )

        all_descendants = self.electronics.get_descendants()
        self.assertEqual(len(all_descendants), 5)

        laptop_descendants = self.laptops.get_descendants()
        self.assertEqual(len(laptop_descendants), 1)
        self.assertIn(self.gaming_laptops, laptop_descendants)

    def test_products_across_hierarchy(self) -> None:
        """Test getting products from category and all subcategories"""
        descendant_categories = [self.computers] + self.computers.get_descendants()
        computer_products = Product.objects.filter(category__in=descendant_categories)

        self.assertEqual(computer_products.count(), 2)
        self.assertIn(self.laptop_product, computer_products)
        self.assertIn(self.gaming_product, computer_products)

    def test_level_update_cascade(self) -> None:
        """Test that changing parent updates levels in entire subtree"""
        # Create new parent at different level
        tablets = Category.objects.create(
            name="Tablets", slug="tablets", parent=self.electronics
        )

        original_laptop_level = self.laptops.level
        original_gaming_level = self.gaming_laptops.level

        self.laptops.parent = tablets
        self.laptops.save()

        self.laptops.refresh_from_db()
        self.gaming_laptops.refresh_from_db()

        self.assertEqual(self.laptops.level, 2)
        self.assertEqual(self.gaming_laptops.level, 3)

    def test_sibling_categories_ordering(self) -> None:
        """Test ordering of sibling categories"""
        sibling1 = Category.objects.create(
            name="Z Sibling", slug="z-sibling", parent=self.electronics, sort_order=2
        )
        sibling2 = Category.objects.create(
            name="A Sibling", slug="a-sibling", parent=self.electronics, sort_order=1
        )
        sibling3 = Category.objects.create(
            name="M Sibling", slug="m-sibling", parent=self.electronics, sort_order=1
        )

        # Get children in order
        children = list(self.electronics.children.all())

        expected_order = ["A Sibling", "Computers", "M Sibling", "Z Sibling"]
        actual_order = [c.name for c in children]

        self.assertEqual(actual_order, expected_order)


class CategoryHierarchyTransactionTest(TransactionTestCase):
    """Integration tests for category hierarchy with transactions"""

    def test_hierarchy_transaction_operations(self) -> None:
        """Test hierarchy operations in transactions"""
        with transaction.atomic():
            electronics = Category.objects.create(
                name="Electronics", slug="electronics"
            )
            computers = Category.objects.create(
                name="Computers", slug="computers", parent=electronics
            )
            laptops = Category.objects.create(
                name="Laptops", slug="laptops", parent=computers
            )

            self.assertEqual(laptops.level, 2)
            self.assertEqual(
                laptops.get_full_path(), "Electronics > Computers > Laptops"
            )

        electronics = Category.objects.create(name="Electronics2", slug="electronics2")

        initial_category_count = Category.objects.count()
        initial_product_count = Product.objects.count()

        try:
            with transaction.atomic():
                computers = Category.objects.create(
                    name="Computers2", slug="computers2", parent=electronics
                )
                Product.objects.create(
                    name="Test Product",
                    sku="TEST-001",
                    price="99.99",
                    category=computers,
                    stock_quantity=5,
                )
                raise Exception("Simulated error")
        except Exception:
            pass

        self.assertEqual(Category.objects.count(), initial_category_count)
        self.assertEqual(Product.objects.count(), initial_product_count)


@pytest.mark.django_db
class CategoryHierarchyPytestTest:
    """Pytest hierarchy tests"""

    def test_hierarchy_operations(self) -> None:
        """Test hierarchy operations with pytest"""
        # Create 3 level hierarchy
        electronics = Category.objects.create(name="Electronics", slug="electronics")
        phones = Category.objects.create(
            name="Phones", slug="phones", parent=electronics
        )
        smartphones = Category.objects.create(
            name="Smartphones", slug="smartphones", parent=phones
        )

        # Create products at different levels
        general_product = Product.objects.create(
            name="General Electronics",
            sku="GEN-001",
            price="99.99",
            category=electronics,
            stock_quantity=10,
        )
        phone_product = Product.objects.create(
            name="Basic Phone",
            sku="PHONE-001",
            price="49.99",
            category=phones,
            stock_quantity=20,
        )
        smart_product = Product.objects.create(
            name="Smartphone",
            sku="SMART-001",
            price="699.99",
            category=smartphones,
            stock_quantity=15,
        )

        assert electronics.level == 0
        assert phones.level == 1
        assert smartphones.level == 2
        assert smartphones.get_full_path() == "Electronics > Phones > Smartphones"

        descendant_categories = [electronics] + electronics.get_descendants()
        all_electronics_products = Product.objects.filter(
            category__in=descendant_categories
        )

        assert all_electronics_products.count() == 3

        single = Category.objects.create(name="Single", slug="single")
        assert single.is_leaf is True
        assert single.get_descendants() == []
        assert single.get_full_path() == "Single"

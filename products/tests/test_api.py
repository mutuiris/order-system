"""
Integration tests for Products API endpoints
"""
from typing import Any
import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from products.models import Category, Product


class CategoryViewSetTest(APITestCase):
    """Test CategoryViewSet API endpoints"""

    def setUp(self) -> None:
        """Set up test data"""
        self.root_category = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        self.child_category = Category.objects.create(
            name='Smartphones',
            slug='smartphones',
            parent=self.root_category
        )
        self.grandchild_category = Category.objects.create(
            name='iPhone',
            slug='iphone',
            parent=self.child_category
        )

    def test_category_endpoints(self) -> None:
        """Test category endpoints"""
        url = reverse('category-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data['results']), 3)
        names = {c['name'] for c in data['results']}
        self.assertTrue({'Electronics', 'Smartphones', 'iPhone'} <= names)

        url = reverse('category-detail', kwargs={'slug': 'electronics'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['slug'], 'electronics')
        self.assertEqual(data['level'], 0)
        self.assertTrue(data['children'])

    def test_category_special_endpoints(self) -> None:
        """Test specialized category endpoints"""
        # tree
        url = reverse('category-tree')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn('tree', data)
        self.assertEqual(data.get('total_categories'), 3)
        self.assertEqual(data['tree'][0]['name'], 'Electronics')
        self.assertEqual(
            data['tree'][0]['children'][0]['children'][0]['name'], 'iPhone'
        )

        Product.objects.create(
            name='iPhone 15', sku='IPH-15', price=Decimal('999.00'),
            category=self.grandchild_category, stock_quantity=10
        )
        Product.objects.create(
            name='Samsung Galaxy', sku='SAM-GAL', price=Decimal('899.00'),
            category=self.child_category, stock_quantity=5
        )
        url = reverse('category-products', kwargs={'slug': 'smartphones'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        products = response.json()['products']
        self.assertEqual(len(products), 2)
        self.assertTrue({'iPhone 15', 'Samsung Galaxy'} <= {p['name'] for p in products})

        # avg price
        url = reverse('category-avg-price', kwargs={'slug': 'smartphones'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data['product_count'], 2)
        self.assertEqual(Decimal(data['average_price']), Decimal('949.00'))

    def test_category_filtering_search(self) -> None:
        """Test category filtering and search"""
        url = reverse('category-list')
        resp = self.client.get(url, {'parent': self.root_category.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Smartphones')

        resp = self.client.get(url, {'search': 'smart'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['name'], 'Smartphones')

    def test_category_error_cases(self) -> None:
        """Test category endpoint error cases"""
        url = reverse('category-detail', kwargs={'slug': 'nonexistent'})
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

        Product.objects.all().delete()
        url = reverse('category-avg-price', kwargs={'slug': 'smartphones'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', resp.json())


class ProductViewSetTest(APITestCase):
    """Test ProductViewSet API endpoints"""

    def setUp(self) -> None:
        """Set up test data"""
        self.category = Category.objects.create(
            name='Test Category',
            slug='test-category'
        )
        self.product = Product.objects.create(
            name='Test Product',
            description='Test description',
            sku='TEST-001',
            price=Decimal('99.99'),
            category=self.category,
            stock_quantity=10
        )

    def test_product_endpoints(self) -> None:
        """Test product endpoints - list and detail"""
        url = reverse('product-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()['results'][0]
        self.assertEqual(data['name'], 'Test Product')
        self.assertEqual(data['sku'], 'TEST-001')
        self.assertEqual(data['category_name'], 'Test Category')

        url = reverse('product-detail', kwargs={'pk': self.product.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data['name'], 'Test Product')
        self.assertTrue(data['is_available'])
        self.assertEqual(data['category']['slug'], 'test-category')

    def test_product_filtering(self) -> None:
        """Test product filtering by various criteria"""
        other_category = Category.objects.create(name='Other Category', slug='other-category')
        Product.objects.create(
            name='Other Product', sku='OTHER-001', price=Decimal('149.99'),
            category=other_category, stock_quantity=5
        )
        Product.objects.create(
            name='Cheap Product', sku='CHEAP-001', price=Decimal('10.00'),
            category=self.category, stock_quantity=5
        )
        Product.objects.create(
            name='Expensive Product', sku='EXP-001', price=Decimal('500.00'),
            category=self.category, stock_quantity=2
        )
        Product.objects.create(
            name='Out of Stock Product', sku='OOS-001', price=Decimal('99.99'),
            category=self.category, stock_quantity=0
        )

        url = reverse('product-list')

        resp = self.client.get(url, {'category': self.category.pk})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()['results']), 4)

        resp = self.client.get(url, {'min_price': '50.00', 'max_price': '150.00'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()['results']), 2)

        resp = self.client.get(url, {'available_only': 'true'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()['results']), 4)

        resp = self.client.get(url, {'search': 'Expensive'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()['results'][0]['name'], 'Expensive Product')

        resp = self.client.get(url, {'ordering': '-price'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        prices = [Decimal(p['price']) for p in resp.json()['results']]
        self.assertEqual(prices[0], Decimal('500.00'))
        self.assertEqual(prices[-1], Decimal('10.00'))

    def test_product_special_endpoints(self) -> None:
        """Test special product endpoints"""
        Product.objects.create(
            name='Low Stock Product', sku='LOW-001', price=Decimal('99.99'),
            category=self.category, stock_quantity=5
        )
        Product.objects.create(
            name='Featured Product', sku='FEAT-001', price=Decimal('149.99'),
            category=self.category, stock_quantity=15
        )

        url = reverse('product-featured')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        names = {p['name'] for p in resp.json()['featured_products']}
        self.assertIn('Test Product', names)
        self.assertIn('Featured Product', names)
        self.assertNotIn('Low Stock Product', names)

        url = reverse('product-availability', kwargs={'pk': self.product.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertTrue(data['is_available'])
        self.assertEqual(data['stock_quantity'], 10)

    def test_product_error_cases(self) -> None:
        """Test product endpoint error cases"""
        url = reverse('product-detail', kwargs={'pk': 99999})
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

        url = reverse('product-list')
        resp = self.client.get(url, {'min_price': 'invalid'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.json()['results']), 1)


@pytest.mark.django_db
class ProductAPIPytestTest:
    """Pytest API tests for products"""

    def test_api_integration(self, api_client: Any) -> None:
        """Test API integration with pytest"""
        category = Category.objects.create(name='Pytest Category', slug='pytest-category')
        Product.objects.create(
            name='Pytest Product', sku='PYTEST-001', price=Decimal('99.99'),
            category=category, stock_quantity=10
        )

        url = reverse('category-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()['results'][0]['name'] == 'Pytest Category'

        url = reverse('product-list')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()['results'][0]
        assert data['name'] == 'Pytest Product'
        assert data['sku'] == 'PYTEST-001'

        Category.objects.create(name='Child', slug='child', parent=category)
        url = reverse('category-tree')
        resp = api_client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['total_categories'] == 2
        assert data['tree'][0]['children'][0]['name'] == 'Child'

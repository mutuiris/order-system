"""
Test data factories for products app
"""
from typing import List, Dict, Any, Tuple
from decimal import Decimal

import factory
from faker import Faker

from factory.declarations import Sequence, LazyAttribute, SubFactory, LazyFunction
from factory.faker import Faker as FactoryFaker
from factory.helpers import post_generation, lazy_attribute

from products.models import Category, Product

fake = Faker()


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory for creating Category instances"""

    class Meta:  # type: ignore[override]
        model = Category
        django_get_or_create = ('slug',)

    name = FactoryFaker('word')
    slug = LazyAttribute(
        lambda obj: f"{obj.name.lower()}-{fake.random_int(1, 999)}")
    sort_order = LazyAttribute(lambda _: 0)
    is_active = True
    parent = None

    @lazy_attribute
    def level(self) -> int:
        """Calculate level based on parent"""
        if self.parent:
            return self.parent.level + 1
        return 0


class RootCategoryFactory(CategoryFactory):
    """Factory for creating root categories"""

    name = Sequence(lambda n: f'Root Category {n}')
    slug = LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
    parent = None
    level = LazyAttribute(lambda _: 0)


class ChildCategoryFactory(CategoryFactory):
    """Factory for creating child categories with parent"""

    name = Sequence(lambda n: f'Child Category {n}')
    slug = LazyAttribute(lambda obj: obj.name.lower().replace(' ', '-'))
    parent = SubFactory(RootCategoryFactory)

    @lazy_attribute
    def level(self) -> int:
        return 1 if self.parent else 0


class ProductFactory(factory.django.DjangoModelFactory):
    """Factory for creating Product instances"""

    class Meta:  # type: ignore[override]
        model = Product
        django_get_or_create = ('sku',)

    name = FactoryFaker('catch_phrase')
    description = FactoryFaker('text', max_nb_chars=200)
    sku = Sequence(lambda n: f'SKU-{n:05d}')
    price = LazyFunction(lambda: Decimal(
        f'{fake.random_int(10, 999)}.{fake.random_int(0, 99):02d}'))
    category = SubFactory(CategoryFactory)
    stock_quantity = FactoryFaker('random_int', min=0, max=100)
    is_active = True

    @post_generation
    def ensure_positive_price(obj: Any, create: bool, extracted: Any, **kwargs: Any) -> None:
        """Ensure price is positive after creation"""
        if create and obj.price <= Decimal('0'):
            obj.price = Decimal('9.99')
            obj.save()


class InStockProductFactory(ProductFactory):
    """Factory for products that are in stock"""

    stock_quantity = FactoryFaker('random_int', min=1, max=100)
    is_active = True


class OutOfStockProductFactory(ProductFactory):
    """Factory for out of stock products"""

    stock_quantity = 0
    is_active = True


class InactiveProductFactory(ProductFactory):
    """Factory for inactive products"""

    is_active = False
    stock_quantity = FactoryFaker('random_int', min=0, max=50)


class ExpensiveProductFactory(ProductFactory):
    """Factory for expensive products"""

    price = LazyFunction(lambda: Decimal(
        f'{fake.random_int(500, 2000)}.{fake.random_int(0, 99):02d}'))
    name = FactoryFaker('catch_phrase')
    description = 'Premium product with advanced features'


class BudgetProductFactory(ProductFactory):
    """Factory for budget products"""

    price = LazyFunction(lambda: Decimal(
        f'{fake.random_int(1, 50)}.{fake.random_int(0, 99):02d}'))
    name = Sequence(lambda n: f'Budget Product {n}')
    description = 'Affordable option with basic features'


# Utility functions for basic test scenarios
def create_category_hierarchy(depth: int = 3, children_per_level: int = 2) -> Dict[str, List[Category]]:
    """
    Create a category hierarchy with specified depth and breadth
    """
    hierarchy: Dict[str, List[Category]] = {}

    # Create root categories
    root_categories: List[Category] = [RootCategoryFactory(
        name=f'Root {i}') for i in range(children_per_level)]
    hierarchy['roots'] = root_categories

    current_level: List[Category] = root_categories

    for level in range(1, depth):
        next_level: List[Category] = []

        for parent in current_level:
            children: List[Category] = [
                CategoryFactory(name=f'{parent.name} Child {i}', parent=parent)
                for i in range(children_per_level)
            ]
            next_level.extend(children)

        hierarchy[f'level_{level}'] = next_level
        current_level = next_level

    return hierarchy


def create_products_in_category(category: Category, count: int = 5, **kwargs: Any) -> List[Product]:
    """
    Create multiple products in a specific category
    """
    products: List[Product] = []

    for i in range(count):
        product_kwargs = kwargs.copy()
        product_kwargs.setdefault('name', f'{category.name} Product {i}')
        product_kwargs['category'] = category

        product = ProductFactory(**product_kwargs)
        products.append(product)

    return products


def create_product_price_range(category: Category, min_price: float = 10.0, max_price: float = 1000.0, count: int = 10) -> List[Product]:
    """
    Create products with prices distributed across a range
    """
    products: List[Product] = []
    price_step = (max_price - min_price) / count

    for i in range(count):
        price = Decimal(f'{min_price + (i * price_step):.2f}')
        product = ProductFactory(
            category=category, price=price, name=f'Product {i} - ${price}')
        products.append(product)

    return products


def create_stock_test_products(category: Category) -> Dict[str, List[Product]]:
    """
    Create products with various stock levels for testing
    """
    return {
        'in_stock': [InStockProductFactory(category=category, stock_quantity=i) for i in range(1, 11)],
        'out_of_stock': [OutOfStockProductFactory(category=category) for _ in range(3)],
        'high_stock': [InStockProductFactory(category=category, stock_quantity=i) for i in range(50, 101, 10)],
    }


# Builder pattern for complex test scenarios
class CategoryHierarchyBuilder:
    """Builder for creating complex category hierarchies"""

    def __init__(self) -> None:
        self.root_name = 'Test Root'
        self.levels: List[Tuple[str, int]] = []

    def with_root(self, name: str) -> 'CategoryHierarchyBuilder':
        """Set root category name"""
        self.root_name = name
        return self

    def add_level(self, name_pattern: str, count: int = 2) -> 'CategoryHierarchyBuilder':
        """Add a level to the hierarchy"""
        self.levels.append((name_pattern, count))
        return self

    def build(self) -> Dict[str, Any]:
        """Build the category hierarchy"""
        result: Dict[str, Any] = {'categories': [], 'by_level': {}}

        # Create root
        root = RootCategoryFactory(name=self.root_name)
        result['root'] = root
        result['categories'].append(root)
        result['by_level'][0] = [root]

        current_parents: List[Category] = [root]

        for level_idx, (name_pattern, count) in enumerate(self.levels, 1):
            level_categories: List[Category] = []

            for parent in current_parents:
                for i in range(count):
                    child_name = name_pattern.format(
                        parent=parent.name, index=i)
                    child = CategoryFactory(name=child_name, parent=parent)
                    level_categories.append(child)
                    result['categories'].append(child)

            result['by_level'][level_idx] = level_categories
            current_parents = level_categories

        return result


class ProductCatalogBuilder:
    """Builder for creating product catalogs with categories"""

    def __init__(self) -> None:
        self.categories: List[Category] = []
        self.products_per_category = 5
        self.product_configs: List[Dict[str, Any]] = []

    def with_categories(self, *category_names: str) -> 'ProductCatalogBuilder':
        """Add categories to the catalog"""
        for name in category_names:
            slug = name.lower().replace(' ', '-')
            category = CategoryFactory(name=name, slug=slug)
            self.categories.append(category)
        return self

    def with_products_per_category(self, count: int) -> 'ProductCatalogBuilder':
        """Set number of products per category"""
        self.products_per_category = count
        return self

    def add_product_config(self, **kwargs: Any) -> 'ProductCatalogBuilder':
        """Add specific product configuration"""
        self.product_configs.append(kwargs)
        return self

    def build(self) -> Dict[str, Any]:
        """Build the product catalog"""
        result: Dict[str, Any] = {
            'categories': self.categories,
            'products': [],
            'products_by_category': {}
        }

        for category in self.categories:
            category_products = create_products_in_category(
                category, self.products_per_category)
            result['products'].extend(category_products)
            result['products_by_category'][category.name] = category_products

        # Add configured products
        for config in self.product_configs:
            if 'category' not in config and self.categories:
                config['category'] = self.categories[0]

            product = ProductFactory(**config)
            result['products'].append(product)

        return result


# Performance testing helpers
def create_large_category_tree(root_name: str = 'Performance Root', max_depth: int = 5) -> Dict[str, Any]:
    """
    Create a large category tree for performance testing
    """
    categories_data: List[Category] = []

    # Build tree level by level
    root = RootCategoryFactory(name=root_name)
    categories_data.append(root)
    current_level: List[Category] = [root]

    for depth in range(1, max_depth + 1):
        next_level: List[Category] = []
        # Fewer children at deeper levels
        children_per_parent = max(1, 10 - depth)

        for parent in current_level:
            for i in range(children_per_parent):
                child = CategoryFactory(
                    name=f'{parent.name} L{depth}C{i}', parent=parent)
                categories_data.append(child)
                next_level.append(child)

        current_level = next_level

    return {
        'root': root,
        'all_categories': categories_data,
        'leaf_categories': current_level,
        'total_count': len(categories_data),
    }


def create_bulk_products(categories: List[Category], products_per_category: int = 100) -> List[Product]:
    """
    Create products in bulk for performance testing
    """
    products_data: List[Product] = []

    for category in categories:
        for i in range(products_per_category):
            product = ProductFactory.build(
                name=f'{category.name} Product {i}',
                sku=f'{category.slug}-{i:04d}',
                category=category
            )
            products_data.append(product)

    # Bulk create all products
    products = Product.objects.bulk_create(products_data)
    return products


def create_ecommerce_catalog() -> Dict[str, Any]:
    """Create a commerce catalog structure"""
    builder = CategoryHierarchyBuilder()

    electronics = (
        builder.with_root('Electronics')
        .add_level('{parent} - Smartphones', 1)
        .add_level('{parent} - {index} Brand', 3)
        .build()
    )

    # Add products to leaf categories
    leaf_categories: List[Category] = electronics['by_level'][2]
    catalog_products: List[Product] = []

    for category in leaf_categories:
        products = create_products_in_category(category, 5)
        catalog_products.extend(products)

    return {
        'hierarchy': electronics,
        'products': catalog_products,
        'total_categories': len(electronics['categories']),
        'total_products': len(catalog_products),
    }


def create_pricing_test_data() -> Dict[str, Any]:
    """Create test data for pricing calculations"""
    category = CategoryFactory(name='Pricing Test Category')

    products = [
        ProductFactory(category=category, price=Decimal(
            '10.00'), name='Budget Item'),
        ProductFactory(category=category, price=Decimal(
            '50.00'), name='Mid-range Item'),
        ProductFactory(category=category, price=Decimal(
            '100.00'), name='Premium Item'),
        ProductFactory(category=category, price=Decimal(
            '500.00'), name='Luxury Item'),
    ]

    return {
        'category': category,
        'products': products,
        'expected_average': Decimal('165.00'),
        'expected_min': Decimal('10.00'),
        'expected_max': Decimal('500.00'),
    }

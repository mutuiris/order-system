from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from django.db.models import QuerySet


class Category(models.Model):
    """
    Hierarchical category model with unlimited depth.
    Supports trees like: Grocery > Produce > Fruits > Citrus > Oranges
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True)

    # Self referencing foreign key for hierarchy
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )

    # Type hints for Pylance
    if TYPE_CHECKING:
        children: 'QuerySet[Category]'
        id: int

    # Denormalized field to optimize queries
    level = models.PositiveIntegerField(default=0)

    # Order categories within the same level
    sort_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        unique_together = [['parent', 'name']]

    def __str__(self):
        """Show full category path for clarity"""
        return self.name

    def save(self, *args, **kwargs):
        """Auto calculate level based on parent hierarchy with preemptive uniqueness checks"""
        from django.db.utils import IntegrityError as DBIntegrityError
        # Capture previous level for existing records
        old_level = None
        if self.pk:
            try:
                old_level = Category.objects.only('level').get(pk=self.pk).level
            except Category.DoesNotExist:
                old_level = None

        if not self.pk:
            if Category.objects.filter(slug=self.slug).exists():
                raise DBIntegrityError(
                    'UNIQUE constraint failed: products_category.slug')
            if Category.objects.filter(parent=self.parent, name=self.name).exists():
                raise DBIntegrityError(
                    'UNIQUE constraint failed: products_category.parent, name')

        # Calculate level
        if self.parent:
            self.level = (self.parent.level or 0) + 1
        else:
            self.level = 0

        super().save(*args, **kwargs)

        if old_level is not None and old_level != self.level:
            level_diff = self.level - old_level
            self.children.update(level=models.F('level') + level_diff)

    def get_full_path(self):
        """Get complete path from root to this category"""
        path = []
        current = self
        visited = set()
        while current and current.id not in visited:
            visited.add(current.id)
            path.append(current.name)
            current = current.parent
        if current and current.id in visited:
            path.append(f"[CIRCULAR: {current.name}]")
        return ' > '.join(reversed(path))

    def get_descendants(self):
        """Get all subcategories recursively with circular reference protection"""
        descendants: List['Category'] = []
        visited: set[int] = set()
        self._collect_descendants(descendants, visited)
        return descendants

    def _collect_descendants(self, descendants: List['Category'], visited: set[int]) -> None:
        """Recursively collect descendants with cycle detection"""
        if self.id in visited:
            return

        visited.add(self.id)
        for child in self.children.all():
            descendants.append(child)
            child._collect_descendants(descendants, visited)

    def get_display_name(self):
        """Get full category path for display (safe to use in templates/admin)"""
        path = []
        current = self
        visited = set()

        while current and current.id not in visited:
            visited.add(current.id)
            path.append(current.name)
            current = current.parent

        if current and current.id in visited:
            path.append(f"[CIRCULAR: {current.name}]")

        return ' > '.join(reversed(path))

    @property
    def is_leaf(self):
        """Check if this category has no children"""
        return not self.children.exists()


class Product(models.Model):
    """
    Product model linked to hierarchical categories.
    Uses decimal for precise price calculations.
    """

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Stock Keeping Unit which is the unique identifier for inventory
    sku = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique product identifier for inventory tracking"
    )

    # Use DecimalField for money
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    # Link to category hierarchy
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )

    # Inventory management
    stock_quantity = models.PositiveIntegerField(default=0)

    # Product status
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this product is available for sale"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_in_stock(self):
        """Check if product is available for purchase"""
        return self.stock_quantity > 0 and self.is_active

    def reduce_stock(self, quantity):
        """Reduce stock when order is placed"""
        if self.stock_quantity >= quantity:
            self.stock_quantity -= quantity
            self.save()
            return True
        return False

"""Tests for camelCase serialization in mappers (FDS-37)."""

from unittest.mock import MagicMock, patch

from src.modules.orders.api.mappers import _camelize_keys, _to_camel, to_order_response
from src.modules.orders.model.delivery_address import DeliveryAddress
from src.modules.orders.model.order import Order
from src.modules.orders.model.order_item import OrderItem
from src.modules.orders.model.order_status import OrderStatus


class TestToCamel:
    def test_order_id(self):
        assert _to_camel("order_id") == "orderId"

    def test_unit_price(self):
        assert _to_camel("unit_price") == "unitPrice"

    def test_single_word(self):
        assert _to_camel("status") == "status"


class TestCamelizeKeys:
    def test_flat_dict(self):
        result = _camelize_keys({"order_id": "123", "customer_id": "456"})
        assert result == {"orderId": "123", "customerId": "456"}

    def test_nested_dict(self):
        result = _camelize_keys(
            {
                "order_id": "1",
                "delivery_address": {
                    "postal_code": "12345",
                    "address_id": "addr-1",
                },
            }
        )
        assert result == {
            "orderId": "1",
            "deliveryAddress": {
                "postalCode": "12345",
                "addressId": "addr-1",
            },
        }

    def test_list_of_dicts(self):
        result = _camelize_keys(
            {
                "items": [
                    {"menu_item_id": "m1", "unit_price": 10.0},
                    {"menu_item_id": "m2", "unit_price": 20.0},
                ],
            }
        )
        assert result == {
            "items": [
                {"menuItemId": "m1", "unitPrice": 10.0},
                {"menuItemId": "m2", "unitPrice": 20.0},
            ],
        }

    def test_nested_dict_with_list_of_dicts(self):
        """camelize_keys converts keys at every level of nested structure."""
        result = _camelize_keys(
            {
                "order_id": "1",
                "items": [
                    {"menu_item_id": "m1", "unit_price": 10.0},
                ],
                "delivery_address": {
                    "postal_code": "12345",
                },
            }
        )
        assert result == {
            "orderId": "1",
            "items": [
                {"menuItemId": "m1", "unitPrice": 10.0},
            ],
            "deliveryAddress": {
                "postalCode": "12345",
            },
        }

    def test_primitives_passthrough(self):
        assert _camelize_keys(42) == 42
        assert _camelize_keys("hello") == "hello"
        assert _camelize_keys(None) is None


class TestToOrderResponse:
    def _make_order(self):
        """Build a minimal Order for testing serialization."""
        item = OrderItem(
            menu_item_id="item-1",
            name="Falafel",
            quantity=2,
            unit_price=15.0,
            line_total=30.0,
        )
        address = DeliveryAddress(
            address_id="addr-1",
            street="Main St",
            city="Tel Aviv",
            postal_code="12345",
        )
        return Order(
            order_id="order-uuid-1",
            customer_id="cust-1",
            restaurant_id="rest-1",
            items=[item],
            delivery_address=address,
            status=OrderStatus.PAID,
            subtotal=30.0,
            currency="ILS",
            created_at="2026-07-25T10:00:00Z",
            updated_at="2026-07-25T11:00:00Z",
        )

    @patch("src.modules.orders.api.mappers.payment_repository")
    def test_has_camelcase_keys_and_not_snakecase(self, mock_repo):
        """Output contains orderId, customerId, approvalUrl; not order_id, customer_id, approval_url."""
        mock_repo.get_by_order_id.return_value = None
        order = self._make_order()
        result = to_order_response(order)

        # Must have camelCase keys
        assert "orderId" in result
        assert "customerId" in result
        assert "approvalUrl" in result

        # Must NOT have snake_case keys
        assert "order_id" not in result
        assert "customer_id" not in result
        assert "approval_url" not in result

    @patch("src.modules.orders.api.mappers.payment_repository")
    def test_items_have_camelcase_keys(self, mock_repo):
        mock_repo.get_by_order_id.return_value = None
        order = self._make_order()
        result = to_order_response(order)

        item = result["items"][0]
        assert "menuItemId" in item
        assert "unitPrice" in item
        assert "lineTotal" in item
        assert "menu_item_id" not in item
        assert "unit_price" not in item
        assert "line_total" not in item

    @patch("src.modules.orders.api.mappers.payment_repository")
    def test_delivery_address_has_camelcase_keys(self, mock_repo):
        mock_repo.get_by_order_id.return_value = None
        order = self._make_order()
        result = to_order_response(order)

        addr = result["deliveryAddress"]
        assert "postalCode" in addr
        assert "addressId" in addr
        assert "postal_code" not in addr
        assert "address_id" not in addr

    @patch("src.modules.orders.api.mappers.payment_repository")
    def test_approval_url_null_when_no_payment(self, mock_repo):
        mock_repo.get_by_order_id.return_value = None
        order = self._make_order()
        result = to_order_response(order)

        assert result["approvalUrl"] is None

    @patch("src.modules.orders.api.mappers.payment_repository")
    def test_approval_url_when_payment_exists(self, mock_repo):
        mock_payment = MagicMock()
        mock_payment.approval_url = "https://paypal.com/checkout/abc"
        mock_repo.get_by_order_id.return_value = mock_payment

        order = self._make_order()
        result = to_order_response(order)

        assert result["approvalUrl"] == "https://paypal.com/checkout/abc"

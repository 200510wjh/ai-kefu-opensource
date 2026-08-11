from __future__ import annotations

import unittest

from desktop_agent.adapters.base import ActiveTarget
from desktop_agent.config import AgentConfig
from desktop_agent.connectors.douyin_dm import DouyinDMConnector


class DouyinDMConnectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = DouyinDMConnector()
        self.config = AgentConfig(
            platform="douyin_dm",
            authorized_account="TestShop",
            contact_allowlist=["TestBuyer"],
            min_chat_chars=2,
        )
        self.target = ActiveTarget("1", "TestBuyer - Douyin DM", "douyin_dm", "douyin_dm", "Douyin DM")

    def test_merges_last_customer_messages(self) -> None:
        prepared = self.connector.prepare_message(
            "Account: TestShop\nContact: TestBuyer\ncustomer: hello\ncustomer: I want the Workspace V1\nseller: ok\ncustomer: does it support website chat?\ncustomer: can it log conversations?",
            self.target,
            self.config,
        )

        self.assertTrue(prepared.should_upload)
        self.assertEqual(prepared.message_text, "does it support website chat?\ncan it log conversations?")
        self.assertEqual(prepared.metadata["contact"], "TestBuyer")
        self.assertEqual(prepared.metadata["last_message_direction"], "customer")
        self.assertEqual(prepared.metadata["merged_message_count"], 2)
        self.assertFalse(prepared.metadata["connector_safety"]["block_auto_send"])  # type: ignore[index]

    def test_skips_own_last_message(self) -> None:
        prepared = self.connector.prepare_message(
            "Account: TestShop\nContact: TestBuyer\ncustomer: hello\nseller: thanks, I replied",
            self.target,
            self.config,
        )

        self.assertFalse(prepared.should_upload)
        self.assertEqual(prepared.reason, "last_message_from_self")

    def test_blocks_non_whitelisted_contact(self) -> None:
        prepared = self.connector.prepare_message(
            "Account: TestShop\nContact: OtherBuyer\ncustomer: hello, can I buy it?",
            self.target,
            self.config,
        )

        safety = prepared.metadata["connector_safety"]  # type: ignore[index]
        self.assertTrue(safety["block_auto_send"])  # type: ignore[index]
        self.assertIn("contact_not_whitelisted", safety["risk_flags"])  # type: ignore[index]

    def test_unsupported_media_handoff(self) -> None:
        prepared = self.connector.prepare_message(
            "Account: TestShop\nContact: TestBuyer\ncustomer: [image]\ncustomer: product card",
            self.target,
            self.config,
        )

        safety = prepared.metadata["connector_safety"]  # type: ignore[index]
        self.assertTrue(safety["block_auto_send"])  # type: ignore[index]
        self.assertIn("unsupported_image", safety["risk_flags"])  # type: ignore[index]

    def test_requires_authorized_account_verification(self) -> None:
        prepared = self.connector.prepare_message(
            "Contact: TestBuyer\ncustomer: hello",
            self.target,
            self.config,
        )

        safety = prepared.metadata["connector_safety"]  # type: ignore[index]
        self.assertTrue(safety["block_auto_send"])  # type: ignore[index]
        self.assertIn("authorized_account_not_verified", safety["risk_flags"])  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()

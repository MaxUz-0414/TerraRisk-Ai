from .base import ServiceTest, registry


class ChatbotTests(ServiceTest):
    def setUp(self):
        super().setUp()
        self.bot = registry.client("chatbot")

    def chat(self, message, **context):
        return self.bot.post("/v1/chat", json={"message": message, "context": context}).json()

    def test_answers_common_questions(self):
        self.assertFalse(self.chat("how much does it cost? what are the plans")["unanswered"])
        self.assertFalse(self.chat("what does the risk score mean")["unanswered"])

    def test_personal_details_come_from_the_context(self):
        reply = self.chat("how many searches do I have left", balance="You have 7 searches left.")
        self.assertIn("7 searches", reply["reply"])

    def test_nonsense_is_marked_unanswered_with_suggestions(self):
        reply = self.chat("qwertyuiop zxcvbnm lkjhgf")
        self.assertTrue(reply["unanswered"])
        self.assertTrue(reply["suggestions"])

    def test_empty_message_is_rejected(self):
        from tr_common.client import ServiceError

        with self.assertRaises(ServiceError) as caught:
            self.bot.post("/v1/chat", json={"message": "   "})
        self.assertEqual(caught.exception.status, 400)

    def test_faq(self):
        faq = self.bot.post("/v1/faq", json={"context": {"support_email": "help@x.org"}}).json()["faq"]
        self.assertGreater(len(faq), 3)
        self.assertTrue(all(item["q"] and item["a"] for item in faq))

import pytest
from playwright.sync_api import Page, expect

def test_feedback_ui_flow(authenticated_page: Page):
    """
    TC-AI-FEEDBACK-01: Verify Feedback UI flow
    1. Navigate to AI page
    2. Switch to Troubleshoot mode
    3. Inject AI message (simulating response)
    4. Verify feedback buttons appear
    5. Click Thumbs Up
    6. Verify success state and API call
    """
    # 1. Navigate — /ai redirects to /troubleshoot which is always in troubleshoot mode
    authenticated_page.goto("/troubleshoot")

    # Wait for the chat UI to load
    authenticated_page.wait_for_selector("#chatMessages", state="visible", timeout=10000)

    # Mock the feedback API to verify the call happens without hitting real DB
    feedback_captured = []
    def handle_feedback(route):
        feedback_captured.append(route.request.post_data_json)
        route.fulfill(
            status=201,
            content_type="application/json",
            body='{"id": "test-id", "message": "Result OK"}'
        )

    authenticated_page.route("**/api/v1/solution-feedback", handle_feedback)

    # 2. Inject AI message matching the current troubleshoot_chat.js DOM structure
    TEST_MESSAGE = "This is a test AI solution for feedback."
    authenticated_page.evaluate(f"""
        (() => {{
            const container = document.getElementById('chatMessages');
            const messageId = 'test-uuid-123';
            const wrapper = document.createElement('div');
            wrapper.className = 'flex justify-start w-full pr-2';
            wrapper.innerHTML = `
                <div class="ai-message-wrapper w-full">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center">
                            <div class="w-6 h-6 rounded-full bg-gradient-to-r from-purple-600 to-blue-600 flex items-center justify-center mr-2">
                                <i class="fas fa-robot text-white text-xs"></i>
                            </div>
                            <span class="text-xs text-gray-400">AI Assistant</span>
                        </div>
                        <div class="feedback-buttons" id="feedback-${{messageId}}">
                            <button onclick="submitFeedback('${{messageId}}', true, this)"
                                    class="text-xs text-gray-500 hover:text-green-400 px-2 py-1 transition-colors"
                                    title="This solution was helpful">
                                <i class="fas fa-thumbs-up"></i>
                            </button>
                            <button onclick="submitFeedback('${{messageId}}', false, this)"
                                    class="text-xs text-gray-500 hover:text-red-400 px-2 py-1 transition-colors"
                                    title="This solution didn't help">
                                <i class="fas fa-thumbs-down"></i>
                            </button>
                        </div>
                    </div>
                    <div class="bg-gray-800/80 rounded-lg p-4 border border-gray-700 text-sm ai-message-content shadow-lg"
                         data-full-text="{TEST_MESSAGE}" data-message-id="${{messageId}}">
                        {TEST_MESSAGE}
                    </div>
                </div>
            `;
            container.appendChild(wrapper);
        }})()
    """)
    
    # 3. Verify feedback buttons are visible
    feedback_section = authenticated_page.locator("#feedback-test-uuid-123")
    expect(feedback_section).to_be_visible()

    thumbs_up = feedback_section.locator(".fa-thumbs-up").locator("..")  # Parent button

    # 4. Click Thumbs Up
    thumbs_up.click()

    # 5. Verify Success State
    expect(feedback_section).to_contain_text("Thanks for feedback!")
    expect(feedback_section.locator(".fa-check")).to_be_visible()

    # 6. Verify API Call
    assert len(feedback_captured) == 1
    data = feedback_captured[0]
    assert data["success"] is True
    assert data["solution_reference"] == TEST_MESSAGE
    # No preceding user message so the fallback "AI Context: ..." path is exercised.

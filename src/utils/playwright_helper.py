"""
Playwright Helper - Browser automation for form filling and application submission
Handles CAPTCHA detection, anti-bot safe typing, screenshots, and error recovery
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class PlaywrightHelper:
    """Browser automation with safety and anti-detection features"""

    def __init__(self, headless: bool = True, screenshots_dir: str = "screenshots"):
        self.headless = headless
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def initialize(self):
        """Initialize browser and context"""

        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-resources',
                ]
            )

            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            self.page = await self.context.new_page()

            # Set viewport
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

            logger.info("✅ Playwright browser initialized")

        except Exception as e:
            logger.error(f"Error initializing Playwright: {e}")
            raise

    async def close(self):
        """Close browser and context"""

        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()

            logger.info("✅ Browser closed")

        except Exception as e:
            logger.error(f"Error closing browser: {e}")

    async def navigate_to(self, url: str) -> bool:
        """Navigate to URL with retry logic"""

        try:
            if not self.page:
                raise RuntimeError("Browser not initialized")

            await self.page.goto(url, wait_until="networkidle", timeout=30000)
            logger.info(f"✅ Navigated to {url}")
            return True

        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            return False

    async def move_mouse_randomly(self):
        """Simulate human-like random mouse movements"""
        if not self.page:
            return

        try:
            # Get viewport size
            viewport = self.page.viewport_size
            if not viewport:
                return

            width, height = viewport["width"], viewport["height"]
            
            # Move to 3-5 random points
            for _ in range(random.randint(3, 5)):
                x = random.randint(0, width)
                y = random.randint(0, height)
                await self.page.mouse.move(x, y, steps=random.randint(5, 15))
                await asyncio.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            logger.warning(f"Error moving mouse: {e}")

    async def fill_form_field(
        self,
        field_name: str,
        field_value: str,
        field_type: str = "text",
    ) -> bool:
        """
        Fill form field with anti-bot safe typing and mouse movements
        """

        try:
            if not self.page:
                return False

            # Find the field
            selector = f'input[name="{field_name}"], input[id="{field_name}"], textarea[name="{field_name}"]'
            field = await self.page.query_selector(selector)

            if not field:
                logger.warning(f"Field not found: {field_name}")
                return False

            # Anti-bot: Move mouse toward the field
            box = await field.bounding_box()
            if box:
                await self.page.mouse.move(
                    box["x"] + box["width"] / 2, 
                    box["y"] + box["height"] / 2,
                    steps=10
                )

            # Anti-bot: Random delay before typing
            await asyncio.sleep(random.uniform(0.5, 1.5))

            if field_type == "select":
                # Handle dropdown
                await self.page.select_option(selector, field_value)
            elif field_type == "checkbox":
                # Handle checkbox
                if field_value.lower() in ["true", "yes", "1"]:
                    await field.check()
            else:
                # Type text with natural speed (50-150ms per character)
                await field.fill("")  # Clear first
                for char in field_value:
                    await field.type(char, delay=random.uniform(50, 150))

            logger.info(f"✅ Filled field: {field_name}")
            return True

        except Exception as e:
            logger.error(f"Error filling field {field_name}: {e}")
            return False

    async def detect_captcha(self) -> bool:
        """Detect if CAPTCHA is present on page"""

        try:
            if not self.page:
                return False

            # Check for common CAPTCHA indicators
            captcha_selectors = [
                'iframe[src*="recaptcha"]',
                'div.g-recaptcha',
                'iframe[title*="recaptcha"]',
                'div.h-captcha',
                'iframe[src*="hcaptcha"]',
            ]

            for selector in captcha_selectors:
                if await self.page.query_selector(selector):
                    logger.warning(f"⚠️ CAPTCHA detected: {selector}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error detecting CAPTCHA: {e}")
            return False

    async def take_screenshot(self, name: str) -> Optional[str]:
        """Take screenshot for evidence"""

        try:
            if not self.page:
                return None

            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            screenshot_path = self.screenshots_dir / f"{name}_{timestamp}.png"

            await self.page.screenshot(path=str(screenshot_path))
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
            return str(screenshot_path)

        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None

    async def submit_form(self, submit_button_selector: Optional[str] = None) -> bool:
        """
        Submit form with anti-bot delays

        Args:
            submit_button_selector: CSS selector for submit button
        """

        try:
            if not self.page:
                return False

            # Anti-bot: Move mouse randomly and then to the button
            await self.move_mouse_randomly()
            
            if submit_button_selector:
                button = await self.page.query_selector(submit_button_selector)
                if button:
                    box = await button.bounding_box()
                    if box:
                        await self.page.mouse.move(
                            box["x"] + box["width"] / 2, 
                            box["y"] + box["height"] / 2,
                            steps=10
                        )
                    await button.click()
                else:
                    logger.error(f"Submit button not found: {submit_button_selector}")
                    return False
            else:
                # Try to find submit button
                submit_button = await self.page.query_selector(
                    'button[type="submit"], input[type="submit"]'
                )
                if submit_button:
                    box = await submit_button.bounding_box()
                    if box:
                        await self.page.mouse.move(
                            box["x"] + box["width"] / 2, 
                            box["y"] + box["height"] / 2,
                            steps=10
                        )
                    await submit_button.click()
                else:
                    logger.error("No submit button found")
                    return False

            # Wait for navigation
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass  # Some pages don't have networkidle state

            logger.info("✅ Form submitted")
            return True

        except Exception as e:
            logger.error(f"Error submitting form: {e}")
            return False

    async def detect_form_fields(self) -> Dict[str, Dict[str, Any]]:
        """
        Detect all form fields on page and their types

        Returns: {field_name: {type, required, placeholder, ...}}
        """

        try:
            if not self.page:
                return {}

            fields = {}

            # Get all input fields
            inputs = await self.page.query_selector_all('input')
            for input_elem in inputs:
                name = await input_elem.get_attribute('name')
                field_type = await input_elem.get_attribute('type') or 'text'
                required = await input_elem.get_attribute('required')
                placeholder = await input_elem.get_attribute('placeholder')

                if name:
                    fields[name] = {
                        'type': field_type,
                        'required': required is not None,
                        'placeholder': placeholder,
                        'element': input_elem,
                    }

            # Get all textarea fields
            textareas = await self.page.query_selector_all('textarea')
            for textarea in textareas:
                name = await textarea.get_attribute('name')
                required = await textarea.get_attribute('required')
                placeholder = await textarea.get_attribute('placeholder')

                if name:
                    fields[name] = {
                        'type': 'textarea',
                        'required': required is not None,
                        'placeholder': placeholder,
                        'element': textarea,
                    }

            # Get all select fields
            selects = await self.page.query_selector_all('select')
            for select in selects:
                name = await select.get_attribute('name')
                required = await select.get_attribute('required')

                if name:
                    fields[name] = {
                        'type': 'select',
                        'required': required is not None,
                        'element': select,
                    }

            logger.info(f"✅ Detected {len(fields)} form fields")
            return fields

        except Exception as e:
            logger.error(f"Error detecting form fields: {e}")
            return {}

    async def auto_fill_form(self, form_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Auto-fill entire form with data

        Args:
            form_data: {field_name: value}

        Returns:
            {
                "filled": 8,
                "total": 10,
                "failed": ["field1"],
                "captcha_detected": false,
                "success": true
            }
        """

        try:
            if not self.page:
                return {"success": False, "message": "Browser not initialized"}

            # Detect form fields
            form_fields = await self.detect_form_fields()
            total_fields = len(form_fields)

            if total_fields == 0:
                return {"success": False, "message": "No form fields detected"}

            filled = 0
            failed = []

            # Fill each field
            for field_name, field_value in form_data.items():
                field_info = form_fields.get(field_name)

                if not field_info:
                    logger.warning(f"Field not in form: {field_name}")
                    failed.append(field_name)
                    continue

                success = await self.fill_form_field(
                    field_name,
                    field_value,
                    field_info.get('type', 'text')
                )

                if success:
                    filled += 1
                else:
                    failed.append(field_name)

            # Check for CAPTCHA
            captcha_detected = await self.detect_captcha()

            # Take screenshot
            await self.take_screenshot("form_filled")

            return {
                "filled": filled,
                "total": total_fields,
                "failed": failed,
                "captcha_detected": captcha_detected,
                "success": filled > 0,
            }

        except Exception as e:
            logger.error(f"Error auto-filling form: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    async def wait_for_element(self, selector: str, timeout: int = 10000) -> bool:
        """Wait for element to appear on page"""

        try:
            if not self.page:
                return False

            await self.page.wait_for_selector(selector, timeout=timeout)
            return True

        except:
            return False

    async def get_page_content(self) -> Optional[str]:
        """Get page HTML content"""

        try:
            if not self.page:
                return None

            return await self.page.content()

        except Exception as e:
            logger.error(f"Error getting page content: {e}")
            return None


# Singleton instance
playwright_helper = PlaywrightHelper()

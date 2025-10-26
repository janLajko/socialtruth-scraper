const express = require("express");
const puppeteer = require("puppeteer");
const axios = require("axios");

const app = express();
const PORT = process.env.PORT || 3000;

const WEBHOOK_URL = "https://open.larksuite.com/open-apis/bot/v2/hook/e1803d73-77fc-49a9-a392-5648e601cf88";

// ✅ Health check endpoint for Render
app.get("/health", (req, res) => {
  res.status(200).send("OK");
});

// ✅ Non-blocking root trigger
app.get("/", (req, res) => {
  res.status(200).send("Scraping triggered ✅");
  runScraper();
});

// ✅ Scraping logic
async function runScraper() {
  console.log("🔁 Trigger received. Scraping...");

  try {
    const browser = await puppeteer.launch({
      headless: "new",
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.setUserAgent(
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    );

    await page.goto("https://truthsocial.com/@realDonaldTrump", {
      waitUntil: "domcontentloaded",
    });
    await new Promise(resolve => setTimeout(resolve, 3000));

    const modalSelectors = [
      'button[aria-label="Close"]',
      'button[aria-label="Close dialog"]',
      'button[aria-label="Dismiss"]',
      '[data-testid="close-button"]',
      '.modal button[aria-label]',
    ];

    for (const selector of modalSelectors) {
      const handle = await page.$(selector);
      if (handle) {
        await handle.click().catch(() => {});
        await new Promise(resolve => setTimeout(resolve, 500));
        console.log(`🧹 Closed modal via selector ${selector}`);
        break;
      }
    }

    const adRemoved = await page.evaluate(() => {
      let removed = false;
      const divs = Array.from(document.querySelectorAll("div"));
      for (const div of divs) {
        const text = (div.textContent || "").trim();
        if (text.includes("Featured Ad")) {
          const modal = div.closest('[role="dialog"]') || div;
          if (modal && modal.parentElement) {
            modal.parentElement.removeChild(modal);
            removed = true;
          }
        }
      }
      return removed;
    });
    if (adRemoved) {
      console.log("🧹 Removed featured ad overlay by text match");
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    const overlayRemoved = await page.evaluate(() => {
      let removed = false;
      const modal =
        document.querySelector('[role="dialog"]') ||
        document.querySelector('[class*="modal"]');
      if (modal && modal.parentElement) {
        modal.parentElement.removeChild(modal);
        removed = true;
      }
      const overlays = document.querySelectorAll('[data-testid="modal"]');
      overlays.forEach(el => el.remove());
      if (overlays.length > 0) {
        removed = true;
      }
      return removed;
    });
    if (overlayRemoved) {
      console.log("🧹 Removed modal overlay via DOM manipulation");
      await new Promise(resolve => setTimeout(resolve, 500));
    }

    const apiResult = await page.evaluate(async () => {
      const htmlToText = html =>
        (html || "")
          .replace(/<br\s*\/?>/gi, "\n")
          .replace(/<\/p>/gi, "\n")
          .replace(/<p>/gi, "")
          .replace(/<[^>]+>/g, " ")
          .replace(/\s+/g, " ")
          .trim();

      const fetchJson = async (url, params) => {
        const resp = await fetch(url, {
          headers: { accept: "application/json" },
          ...params,
        });
        if (!resp.ok) {
          throw new Error(`${url} -> HTTP ${resp.status}`);
        }
        return resp.json();
      };

      try {
        const account = await fetchJson(
          "/api/v1/accounts/lookup?acct=realDonaldTrump"
        );
        if (!account || !account.id) {
          return { error: "lookup returned unexpected payload" };
        }
        const statuses = await fetchJson(
          `/api/v1/accounts/${account.id}/statuses?exclude_replies=true&limit=1`
        );
        if (!Array.isArray(statuses) || statuses.length === 0) {
          return { error: "no statuses returned" };
        }

        const latest = statuses[0];
        return {
          id: latest.id,
          url: latest.url,
          text: htmlToText(latest.content),
          raw: latest.content,
        };
      } catch (err) {
        return { error: err.message || String(err) };
      }
    });

    await browser.close();

    if (!apiResult || apiResult.error) {
      console.warn(
        "⚠️ Failed to retrieve post via API:",
        apiResult?.error || "unknown error"
      );
      console.log("✅ Latest post:", "⚠️ No post found (API failure)");
      return;
    }

    console.log("✅ Latest post:", apiResult.text);
    if (apiResult.url) {
      console.log("🔗 Link:", apiResult.url);
    }

    if (apiResult.text) {
      const response = await axios.post(WEBHOOK_URL, { post: apiResult.text, url: apiResult.url });
      console.log("✅ Sent to n8n:", response.status);
    }
  } catch (err) {
    console.error("❌ Scraping failed:", err.message);
  }
}

// ✅ Bind to 0.0.0.0 for Render
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Server running on http://0.0.0.0:${PORT}`);
});

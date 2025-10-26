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
      waitUntil: "networkidle2",
    });

    // ⏱ Wait for posts to load
    await new Promise(resolve => setTimeout(resolve, 8000));

    const latestPost = await page.evaluate(() => {
      const postElement = document.querySelector(
        ".status__wrapper .status__content-wrapper p"
      );
      return postElement ? postElement.innerText.trim() : "⚠️ No post found!";
    });

    await browser.close();

    console.log("✅ Latest post:", latestPost);

    if (!latestPost.startsWith("⚠️")) {
    //   const response = await axios.post(WEBHOOK_URL, { post: latestPost });
    //   console.log("✅ Sent to n8n:", response.status);
    } else {
      console.warn("⚠️ No post found");
    }
  } catch (err) {
    console.error("❌ Scraping failed:", err.message);
  }
}

// ✅ Bind to 0.0.0.0 for Render
app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Server running on http://0.0.0.0:${PORT}`);
});
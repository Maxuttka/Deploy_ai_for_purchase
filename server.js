const express = require("express");
const path = require("path");
const multer = require("multer");

const app = express();
const port = process.env.PORT || 3000;
const FASTAPI_URL = process.env.FASTAPI_URL || "http://localhost:8000";

const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 200 * 1024 * 1024 }
});

app.use(express.static(path.join(__dirname, "public")));

app.post("/api/upload", upload.single("file"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "Файл не загружен" });
    }

    const kind = req.body.kind || "orders";

    const formData = new FormData();
    const blob = new Blob([req.file.buffer], { type: req.file.mimetype });
    formData.append("file", blob, req.file.originalname);

    const response = await fetch(`${FASTAPI_URL}/imports/${kind}`, {
      method: "POST",
      body: formData
    });

    const text = await response.text();
    res.status(response.status);

    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка отправки файла в FastAPI:", err);
    res.status(500).json({ error: "Ошибка отправки файла в FastAPI" });
  }
});

app.get("/api/imports", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/imports`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения списка импортов:", err);
    res.status(500).json({ error: "Ошибка получения списка импортов" });
  }
});

app.get("/api/status/:jobId", async (req, res) => {
  try {
    const jobId = req.params.jobId;
    const response = await fetch(`${FASTAPI_URL}/imports/${jobId}`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения статуса:", err);
    res.status(500).json({ error: "Ошибка получения статуса" });
  }
});

app.get("/api/errors/:jobId", async (req, res) => {
  try {
    const jobId = req.params.jobId;
    const response = await fetch(`${FASTAPI_URL}/imports/${jobId}/errors`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения ошибок:", err);
    res.status(500).json({ error: "Ошибка получения ошибок" });
  }
});

app.get("/api/result/:jobId", async (req, res) => {
  try {
    const jobId = req.params.jobId;
    const response = await fetch(`${FASTAPI_URL}/imports/${jobId}/result`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения результата:", err);
    res.status(500).json({ error: "Ошибка получения результата" });
  }
});

app.get("/api/drafts", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/drafts/`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения черновиков:", err);
    res.status(500).json({ error: "Ошибка получения черновиков" });
  }
});

app.post("/api/drafts/items", express.json(), async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/drafts/items`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });

    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
      console.error("Ошибка добавления в черновик:", err);
      res.status(500).json({ error: "Ошибка добавления в черновик" });
  }
});

app.get("/api/drafts/:id", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/drafts/${req.params.id}`);
    const text = await response.text();
    res.status(response.status);
    try { res.json(JSON.parse(text)); } catch { res.send(text); }
  } catch (err) {
    res.status(500).json({ error: "Ошибка получения черновика" });
  }
});

app.put("/api/drafts/:id", express.json(), async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/drafts/${req.params.id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });
    const text = await response.text();
    res.status(response.status);
    try { res.json(JSON.parse(text)); } catch { res.send(text); }
  } catch (err) {
    res.status(500).json({ error: "Ошибка сохранения" });
  }
});

app.delete("/api/drafts/:id", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/drafts/${req.params.id}`, {
      method: "DELETE"
    });

    const text = await response.text();
    res.status(response.status);

    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка удаления черновика:", err);
    res.status(500).json({ error: "Ошибка удаления черновика" });
  }
});

app.get("/api/drafts/:id/email-template", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/drafts/${req.params.id}/email-template`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения шаблона письма:", err);
    res.status(500).json({ error: "Ошибка получения шаблона письма" });
  }
});

app.get("/api/suppliers", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/suppliers/`);
    const text = await response.text();

    res.status(response.status);
    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка получения поставщиков:", err);
    res.status(500).json({ error: "Ошибка получения поставщиков" });
  }
});

app.post("/api/suppliers", express.json(), async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/suppliers/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req.body),
    });

    const text = await response.text();
    res.status(response.status);

    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка добавления поставщика:", err);
    res.status(500).json({ error: "Ошибка добавления поставщика" });
  }
});

app.delete("/api/suppliers/:id", async (req, res) => {
  try {
    const response = await fetch(`${FASTAPI_URL}/suppliers/${req.params.id}`, {
      method: "DELETE"
    });

    const text = await response.text();
    res.status(response.status);

    try {
      res.json(JSON.parse(text));
    } catch {
      res.send(text);
    }
  } catch (err) {
    console.error("Ошибка удаления поставщика:", err);
    res.status(500).json({ error: "Ошибка удаления поставщика" });
  }
});

app.listen(port, "0.0.0.0", () => {
  console.log(`Frontend server running on port ${port}`);
});
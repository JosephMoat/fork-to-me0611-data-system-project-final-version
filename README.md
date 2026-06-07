# 國立政治大學 資訊科學系 畢業學分驗證系統
(NCCU CS Graduation Credit Verification System)

本系統專為國立政治大學資訊科學系學生設計，旨在自動化解析與驗證學生的修課成績，並視覺化呈現畢業學分門檻達成進度。

## 🌟 系統特色 (Features)

- **🎓 畢業門檻自動驗證**：
  - 精準計算「專業必修 (51學分)」、「專業選修 (49學分)」、「通識大水庫 (28學分)」。
  - 動態對齊政大資科系最新規範（含資訊專題、群修 B~E 歸類為系選修）。
- **📊 視覺化儀表板 (Dashboard)**：
  - 以圓形進度條與直觀的卡片呈現各類別學分達成率。
  - 核心通識跨領域規定（自然、社會、人文）合併檢核與防呆預警。
- **📝 詳細規則清單 (Graduation Rules)**：
  - 一目了然的條列式清單，指出具體缺少哪些必修課與學分。
- **🤖 選課推薦 (Course Recommendation)**：
  - 根據學生尚未滿足的畢業門檻與選課歷史，推薦合適的課程。

## 🚀 技術堆疊 (Tech Stack)

### Frontend (前端)
- React 18
- Vite
- TypeScript
- Tailwind CSS
- Lucide React (Icons)
- React Router DOM

### Backend (後端)
- FastAPI (Python)
- SQLite (資料庫)
- SQLAlchemy (ORM)
- Uvicorn (Server)

## 🛠️ 本地執行指南 (Local Setup)

### 方法一：使用 Docker 快速啟動 (推薦)
透過 Docker，你可以一鍵啟動完整的前後端服務，無須設定環境：
```bash
docker-compose up --build -d
```
啟動後，瀏覽器開啟 `http://localhost:3000` 即可使用系統。(後端 API 會自動在 `http://localhost:8000` 運行)。

---

### 方法二：手動啟動
#### 1. 啟動後端 (Backend)
```bash
cd dbms_final_backend
pip install -r requirements.txt
python seed.py # 初始化資料庫與規則
python -m uvicorn app.main:app --reload --port 8000
```

#### 2. 啟動前端 (Frontend)
```bash
cd graduation-credit-verification-system
npm install
npm run dev
```
瀏覽器開啟 `http://localhost:3000` 即可使用系統。

## 👥 開發團隊
本專案為政大資料庫系統課程 (DBMS) 期末專案。

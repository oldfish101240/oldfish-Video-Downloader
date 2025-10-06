# OldFish 影片下載器 - 重構說明

## 📁 新的檔案結構

```
main/
├── main.py                    # 主程式入口點
├── oldfish_downloader.pyw     # 原始檔案（保留作為備份）
├── settings.pyw              # 設定頁面（保持不變）
├── settings.json             # 設定檔案
├── assets/                   # 資源檔案
├── downloads/                # 下載目錄
├── thumb_cache/              # 縮圖快取
├── python_embed/             # 內嵌 Python 環境
│
├── utils/                    # 工具模組
│   ├── __init__.py
│   ├── logger.py             # 日誌和輸出工具
│   ├── file_utils.py         # 檔案和路徑處理
│   └── version_utils.py      # 版本處理工具
│
├── core/                     # 核心功能模組
│   ├── __init__.py
│   ├── api.py                # 主要 API 類別
│   ├── video_info.py         # 影片資訊處理
│   └── downloader.py         # 下載功能
│
├── config/                   # 配置模組
│   ├── __init__.py
│   ├── constants.py          # 常數定義
│   └── settings.py           # 設定管理
│
└── ui/                       # 使用者介面模組
    ├── __init__.py
    ├── main_window.py        # 主視窗
    └── html_content.py       # HTML 內容
```

## 🔄 重構優勢

### 1. **模組化設計**
- 每個模組職責單一，易於維護
- 降低程式碼耦合度
- 提高程式碼重用性

### 2. **可讀性提升**
- 原始檔案 3716 行 → 分散到多個小檔案
- 每個檔案功能明確
- 便於理解和修改

### 3. **維護性改善**
- 修改特定功能時只需關注對應模組
- 減少意外影響其他功能的風險
- 便於團隊協作開發

### 4. **測試友好**
- 每個模組可以獨立測試
- 便於單元測試和整合測試
- 提高程式碼品質

## 🚀 使用方式

### 啟動新版本
```bash
# 方法1: 使用批次檔（推薦）
start_new_version.bat

# 方法2: 直接使用內嵌 Python
python_embed\pythonw.exe main.py

# 方法3: 使用原始啟動器（需要修改）
oldfish影片下載器.exe
```

### 啟動原始版本（備份）
```bash
python_embed\pythonw.exe oldfish_downloader.pyw
```

## 📋 模組說明

### `utils/` - 工具模組
- **logger.py**: 統一的日誌輸出格式
- **file_utils.py**: 檔案操作和路徑處理
- **version_utils.py**: 版本比較和處理

### `core/` - 核心功能
- **api.py**: 主要的 API 類別，處理前後端通信
- **video_info.py**: 影片資訊提取和處理
- **downloader.py**: 下載功能實現

### `config/` - 配置管理
- **constants.py**: 應用程式常數定義
- **settings.py**: 設定檔案的讀寫管理

### `ui/` - 使用者介面
- **main_window.py**: 主視窗類別和應用程式初始化
- **html_content.py**: HTML 介面內容

## 🔧 遷移指南

1. **保留原始檔案**: `oldfish_downloader.pyw` 作為備份
2. **逐步遷移**: 可以逐步將功能遷移到新架構
3. **測試驗證**: 確保新架構功能正常
4. **清理舊檔案**: 確認無誤後可移除原始檔案

## ⚠️ 注意事項

1. **依賴關係**: 確保所有模組的 import 路徑正確
2. **設定檔案**: 設定檔案格式保持不變
3. **資源檔案**: assets 目錄結構保持不變
4. **向下相容**: 保持與現有設定和資料的相容性

## 🎯 未來改進

1. **錯誤處理**: 增強各模組的錯誤處理機制
2. **日誌系統**: 實現更完善的日誌記錄
3. **配置驗證**: 增加設定檔案的驗證機制
4. **單元測試**: 為各模組添加測試用例
5. **文檔完善**: 添加更詳細的 API 文檔

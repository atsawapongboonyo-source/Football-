# Fooball v0.4.2.2 — Stable app.js Hotfix

Hotfix นี้แก้ปัญหา `app-0421.js` ขึ้น Internal Server Error บน Render โดยกลับมาใช้ชื่อไฟล์ JavaScript มาตรฐาน `app.js` ที่ root และใช้ query-string cache busting แทน

สิ่งที่แก้:
- JavaScript หลักเป็น `/app.js?v=0422`
- `main.py` มี route `/app.js` ที่ส่งไฟล์ `app.js` โดยตรง
- ปิด cache ของ JavaScript ด้วย `Cache-Control: no-store`
- Frontend/API/health version เป็น `0.4.2.2`
- service worker cache key เป็น `fooball-v0422` และยังบังคับ network สำหรับ HTML/JS/API
- Advanced Stats, H2H history และ Prediction vs Actual ยังอยู่ครบ

## วิธี deploy
1. แตก ZIP แล้วอัปโหลดไฟล์ **ทั้งหมด** ไปที่ GitHub root โดยให้แทนที่ไฟล์เดิม
2. ตรวจให้เห็นไฟล์ `app.js` อยู่ระดับเดียวกับ `main.py` และ `index.html`
3. Commit เช่น `Hotfix Fooball v0.4.2.2 stable app js`
4. รอ Render Auto-Deploy
5. ทดสอบ `/health` ต้องเห็น `0.4.2.2`
6. เปิด `/app.js?v=0422` ต้องเห็นโค้ด JavaScript ไม่ใช่ Internal Server Error
7. หน้าเว็บต้องแสดง `Frontend v0.4.2.2 พร้อมใช้งาน` และ dropdown รายชื่อทีมต้องกลับมา

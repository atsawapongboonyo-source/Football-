# Fooball v0.4.3 — Inline Frontend Deployment Fix

รุ่นนี้แก้ปัญหา Browser/Service Worker โหลด `app.js` เก่า (เช่น Frontend v0.3.4) แม้ HTML/Backend จะเป็นรุ่นใหม่

## สิ่งที่เปลี่ยน
- JavaScript หลักถูกฝังไว้ใน `index.html` โดยตรง จึงไม่พึ่งไฟล์ JS ภายนอกในการเริ่มระบบ
- หน้าเว็บจะล้าง Cache Storage และ unregister Service Worker เก่าเมื่อเปิดหน้า
- เพิ่ม `/api/version` สำหรับตรวจว่า Frontend และ Backend เป็นเวอร์ชันเดียวกัน
- `/health` แสดง deployment marker `inline-frontend-043`
- Advanced Stats, H2H และ Prediction vs Actual ยังคงอยู่ครบ
- `app.js` ยังแนบไว้เพื่อ debug แต่หน้าเว็บไม่ต้องใช้ไฟล์นี้

## หลัง Deploy ควรเห็น
- Badge: `V0.4.3`
- ใต้ปุ่ม: `Frontend v0.4.3 · Backend v0.4.3 พร้อมใช้งาน`
- Dropdown มีทีมครบ
- `/health` => version 0.4.3
- `/api/version` => backend/frontend_expected 0.4.3, javascript_mode inline

## Upload
อัปไฟล์ทั้งหมดในโฟลเดอร์นี้ไป GitHub root แล้ว commit เช่น:
`Upgrade Fooball v0.4.3 inline frontend`

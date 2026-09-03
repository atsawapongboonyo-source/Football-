# Fooball v0.4.4 — Inline Frontend Deployment Fix

รุ่นนี้แก้ปัญหา Browser/Service Worker โหลด `app.js` เก่า (เช่น Frontend v0.3.4) แม้ HTML/Backend จะเป็นรุ่นใหม่

## สิ่งที่เปลี่ยน
- JavaScript หลักถูกฝังไว้ใน `index.html` โดยตรง จึงไม่พึ่งไฟล์ JS ภายนอกในการเริ่มระบบ
- หน้าเว็บจะล้าง Cache Storage และ unregister Service Worker เก่าเมื่อเปิดหน้า
- เพิ่ม `/api/version` สำหรับตรวจว่า Frontend และ Backend เป็นเวอร์ชันเดียวกัน
- `/health` แสดง deployment marker `inline-frontend-043`
- Advanced Stats, H2H และ Prediction vs Actual ยังคงอยู่ครบ
- `app.js` ยังแนบไว้เพื่อ debug แต่หน้าเว็บไม่ต้องใช้ไฟล์นี้

## หลัง Deploy ควรเห็น
- Badge: `V0.4.4`
- ใต้ปุ่ม: `Frontend v0.4.4 · Backend v0.4.4 พร้อมใช้งาน`
- Dropdown มีทีมครบ
- `/health` => version 0.4.4
- `/api/version` => backend/frontend_expected 0.4.4, javascript_mode inline

## Upload
อัปไฟล์ทั้งหมดในโฟลเดอร์นี้ไป GitHub root แล้ว commit เช่น:
`Upgrade Fooball v0.4.4 inline frontend`

## v0.4.4 Match Intelligence
- แก้สถานะคู่ที่แข่งจบแล้ว: ถ้าเลือกคู่ที่มีผลในฤดูกาลปัจจุบัน ระบบจะแสดงผลจริงทันทีและระบุว่าเป็น retrospective analysis
- ไม่เอาการวิเคราะห์ย้อนหลังไปปนกับสถิติความแม่นยำของคำทำนายก่อนแข่ง
- บันทึก prediction เฉพาะเมื่อผูกกับโปรแกรมที่ยังไม่จบได้จริง
- `/api/model-performance` สรุป 1X2, Over 2.5, BTTS, exact score และ Brier score จาก prediction ที่มีผลจริง
- ข้อมูลผลการแข่งขันยัง refresh อัตโนมัติทุกประมาณ 1 ชั่วโมงตามแหล่ง Football-Data; ความเร็วหลังจบเกมขึ้นกับการอัปเดตของต้นทาง

> หมายเหตุ: prediction_history.json เป็น local runtime storage สำหรับช่วงทดสอบบน Render Free และอาจหายเมื่อ redeploy/restart. ขั้น production ควรย้ายไป PostgreSQL.

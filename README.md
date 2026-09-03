# Fooball v0.4.5 — Fixture Engine

เวอร์ชันนี้แยก **โปรแกรมการแข่งขันอนาคต** ออกจาก **ข้อมูลผลการแข่งขันย้อนหลัง** เพื่อให้ Fooball สามารถบันทึก prediction ก่อนแข่งจริงได้ แม้ไฟล์ผลการแข่งขันประจำฤดูกาลยังไม่มี future fixture อยู่ใน CSV หลัก

## สิ่งที่เพิ่มใน v0.4.5

- `fixture_engine.py` เป็น Fixture Engine แยกต่างหาก
- Provider หลัก: Football-Data `fixtures.csv` โดยกรอง `Div=E0`
- Provider สำรอง: ESPN public EPL schedule endpoint แบบไม่ใช้ API key
- ไม่อ่าน/ไม่ใช้ราคาต่อรองจาก fixture feed เป็น input ของโมเดล
- `/api/upcoming-fixtures?days=10` ดูโปรแกรมที่ Fixture Engine พบ
- `/api/fixture-status` ตรวจ provider และข้อผิดพลาด
- Prediction snapshot เก็บ `fixture_id`, `kickoff_utc`, `fixture_source`
- ผลจริงยังอ่านจาก Football-Data historical/current-season result feed
- การจับผลจริงยอมให้วันที่ต่าง ±1 วันเฉพาะทีมและ home/away เดิม เพื่อกันปัญหา date-only/timezone
- Frontend แสดงแหล่ง fixture และเวลา kickoff ตาม timezone ของอุปกรณ์ผู้ใช้
- Backend/Frontend version = `0.4.5`

## วิธี Deploy บน Render

แตก ZIP แล้วอัปโหลด **ทุกไฟล์ในโฟลเดอร์นี้ไปที่ GitHub root** ทับไฟล์เดิม จากนั้น commit เช่น:

`Upgrade Fooball v0.4.5 fixture engine`

Render จะ auto-deploy branch `main` ตามเดิม

Build command:

`pip install -r requirements.txt`

Start command:

`uvicorn main:app --host 0.0.0.0 --port $PORT`

## ทดสอบหลัง Deploy

1. เปิด `/health` ต้องเห็น `0.4.5` และ `fixture-engine-045`
2. เปิด `/api/fixture-status` ต้องเห็น provider เช่น `Football-Data Fixtures` หรือ `ESPN Schedule fallback`
3. เปิด `/api/upcoming-fixtures?days=10` ต้องเห็นโปรแกรม EPL ที่กำลังจะถึง
4. เลือก **Manchester City vs Coventry City** แล้วกดวิเคราะห์
5. ถ้า Fixture Engine พบเกม ระบบต้องขึ้น `บันทึกเป็นคำทำนายก่อนแข่งแล้ว`
6. หน้า `คำวิเคราะห์เทียบผลจริง` ต้องมี prediction ที่สถานะรอผล
7. หลังเกมจบและ Football-Data result feed อัปเดต ระบบจะผูกผลจริงอัตโนมัติและนำไปคำนวณหน้า `ผลงานของโมเดล`

## หมายเหตุสำคัญ

`prediction_history.json` ยังอยู่บน local filesystem ของ Render ซึ่งไม่ใช่ persistent storage ระยะยาว การ redeploy/restart อาจทำให้ประวัติหายได้ ดังนั้น milestone ถัดไปที่ควรทำคือ PostgreSQL สำหรับ prediction/result history แบบถาวร

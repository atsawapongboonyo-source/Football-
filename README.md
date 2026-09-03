# Fooball v0.4.7 — Fixture Engine + Probability Range Fix

รอบนี้แก้ 2 จุดต่อจาก v0.4.6 โดยไม่เปลี่ยนแกนโมเดลหลัก

1. **Fixture Engine แข็งแรงขึ้น**
   - Football-Data fixtures.csv ยังเป็นหนึ่งในแหล่งโปรแกรม
   - ESPN schedule ถูก query **ทีละวัน** ตลอด horizon 21 วัน แทนการพึ่ง date-range query เดียว
   - merge + dedupe สองแหล่ง และ normalize ชื่อทีม เช่น Man City / Manchester City FC
   - ใช้วันปัจจุบันตาม Europe/London สำหรับโปรแกรม EPL
   - เพิ่ม `/api/fixture-debug?force=true` เพื่อดู provider, error และ fixtures ที่ backend มองเห็นจริง

2. **ช่วงประตูไม่ใช้ 68% shortest interval แล้ว**
   - เปลี่ยนเป็น discrete equal-tail interval เป้าหมายประมาณ **80%**
   - ตัวอย่าง lambda ใกล้ 1.42 / 1.73 จะอ่านเป็นประมาณ `0–3 | 0–3` แทน `0–2 | 0–2`
   - ช่วงนี้เป็น “ช่วงที่มีความเป็นไปได้หลัก” ไม่ใช่การรับประกันว่าผลต้องอยู่ในช่วงนั้น
   - exact score ยังคงแสดงเป็น Top 3 พร้อม probability เพื่อไม่ให้ผู้ใช้ยึดสกอร์เดียว

## Deploy

อัปไฟล์ทั้งหมดใน ZIP ทับไฟล์เดิมที่ GitHub root แล้ว commit เช่น:

`Upgrade Fooball v0.4.7 fixture probability fix`

Render จะ auto-deploy จาก branch main ตาม setup เดิม

## หลัง deploy ให้ตรวจ

- Badge และ footer เป็น `v0.4.7`
- `/health` คืน version `0.4.7`
- `/api/fixture-status` แสดง `provider_counts`
- เปิด `/api/fixture-debug?force=true` หากหน้า “โปรแกรมพรีเมียร์ลีกถัดไป” ยังว่าง
- ช่วงประตูในหน้าผลวิเคราะห์ระบุ `ช่วงประตูหลัก ≈80%`

## Step ถัดไป

เมื่อ Fixture Engine เห็นโปรแกรมอนาคตและสามารถบันทึก prediction ก่อนแข่งได้แล้ว ค่อยไป v0.4.8 เพื่อทำ Feature Experiment + Walk-forward Backtest ก่อนเอา Shots/SOT/Conversion/ฟอร์มเข้าโมเดล production จริง

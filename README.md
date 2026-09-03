# Fooball v0.4.6 — Prediction Clarity + Fixture Matching

เวอร์ชันนี้ทำ 2 งานตามลำดับก่อนขยับไปโมเดล feature-enhanced:

1. **แก้การตีความสกอร์ 2–1 ซ้ำบ่อย** — หน้าเว็บไม่ยก exact score เป็นคำทำนายหลักอีกต่อไป แต่แสดงช่วงประตูของแต่ละทีม (credible goal band), 1X2, expected goals และให้ exact score เป็นเพียงอันดับความน่าจะเป็น พร้อมแสดง probability mass ของ Top 3.
2. **ทำ Fixture Engine ให้ทนต่อข้อมูลไม่ครบ** — query ทั้ง Football-Data Fixtures และ ESPN แล้ว merge/dedupe แทนการหยุดเมื่อ provider แรกตอบสำเร็จ รวมทั้ง canonical team aliases เช่น Man City / Manchester City FC / Manchester City.
3. **Upcoming Fixtures Dashboard** — หน้าเว็บแสดงโปรแกรม 10 วันข้างหน้าที่ Fixture Engine มองเห็น และกดคู่เพื่อเติม dropdown ได้ทันที.

## Deploy
อัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ไป GitHub root แล้ว commit เช่น:

`Upgrade Fooball v0.4.6 prediction clarity`

Render ใช้ค่าเดิม:
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## หลัง deploy ให้ตรวจ
- badge/footer เป็น v0.4.6
- `/api/version` เป็น 0.4.6
- ส่วน “โปรแกรมพรีเมียร์ลีกถัดไป” มีรายการ fixture ถ้า provider ต้นทางตอบข้อมูล
- Manchester City vs Coventry City ถ้าถูกพบ จะขึ้น fixture และบันทึก prediction ก่อนแข่ง
- ผลวิเคราะห์จะแสดงช่วงประตู เช่น `1–3 | 0–1` และ exact score 2–1 เป็นเพียงสกอร์เด่นพร้อมเปอร์เซ็นต์

## Step ถัดไป (v0.4.7)
ทำ feature experiment/backtest: Shots, SOT, conversion, defensive shot allowance และ form เข้าโมเดลแบบมีการ shrinkage แล้วเปรียบเทียบกับ baseline ด้วย Brier / Log Loss / calibration ก่อนเปิดใช้จริง.

# Fooball v0.5.0 — Goal Prediction Engine

รอบนี้ต่อจาก v0.4.9 โดยคง Fixture Engine / Auto-Analyze / Prediction Tracking ไว้ และปรับการคำนวณสกอร์ให้ใช้บริบทเกมเหย้า-เยือนมากขึ้น

## สิ่งที่เพิ่ม
- เปลี่ยนจุดกลางจากช่วงประตู `1–5 | 0–3` เป็น **สกอร์คาดการณ์** จาก score probability matrix
- เพิ่ม venue goal context สำหรับเจ้าบ้านและทีมเยือน
- ใช้ฟอร์มยิงล่าสุดแบบปรับเล็กน้อย เพื่อไม่ double-count กับโมเดลหลัก
- ใช้ Shots / Shots on Target / shot accuracy / conversion เป็นตัวปรับแบบจำกัดช่วง
- เพิ่ม **Clean Sheet rate + Failed-to-score rate** เป็นตัวปรับ probability ของผลที่ทีมใดทีมหนึ่งยิง 0 โดยตรง
- ทีมเลื่อนชั้นยังใช้ Championship 2025/26 prior/fallback ตามเดิมจนมีข้อมูล EPL เพียงพอ
- Expected goals เปลี่ยนชื่อใน UI เป็น “ประตูเฉลี่ยที่โมเดลคาด” เพื่อไม่ให้สับสนกับสกอร์จริง

## หลักการสำคัญ
Baseline ยังเป็น Recency-weighted Poisson + Dixon-Coles + Elo + promoted-team prior. ชั้น Goal Prediction Engine เป็น contextual adjustment ขนาดเล็กเพื่อหลีกเลี่ยงการนับข้อมูลซ้ำ และยังถือเป็น prototype ที่ต้องผ่าน walk-forward backtest/calibration ก่อนใช้เป็นหลักฐานความแม่นยำ

## Deploy
อัปโหลดไฟล์ทั้งหมดใน ZIP ไปที่ GitHub root แล้ว commit เช่น:

`Upgrade Fooball v0.5.0 goal prediction engine`

Render จะ auto-deploy ตามการตั้งค่าเดิม

หลัง deploy ตรวจ:
1. badge/footer = v0.5.0
2. `/health` = 0.5.0
3. กด Fixture จริงแล้วระบบ auto-analyze
4. ตรงกลางแสดงสกอร์คาดการณ์ เช่น `2–1` แทนช่วง `1–5 | 0–3`
5. ใน “วิธีที่โมเดลนำสถิติมาประกอบ” ต้องเห็น Clean Sheet และยิงไม่ได้ของทั้งสองทีม

# Fooball v0.4.2.1 — Frontend Cache Hotfix

Hotfix หลัง v0.4.2:
- ใช้ไฟล์ JavaScript ชื่อใหม่ `app-0421.js` เพื่อเลี่ยง browser/service-worker cache ของ `app.js` รุ่นเก่า
- แสดง `Frontend v0.4.2.1 พร้อมใช้งาน` ก่อนกดวิเคราะห์ เพื่อเช็กได้ทันทีว่า JS ใหม่ถูกโหลด
- Advanced Match Stats แสดงข้อความชัดเจนเมื่อไม่มี metric แทนกล่องว่าง
- ย้าย `ผลจากการวิเคราะห์` ให้อยู่ก่อน Advanced Stats / H2H / Prediction History
- service worker ล้าง cache เก่าและไม่ cache HTML/JS/API
- `/health` และ API version เป็น `0.4.2.1`

## Deploy
อัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้ทับไฟล์เดิมที่ GitHub root แล้ว commit เช่น:
`Hotfix Fooball v0.4.2.1 frontend cache`

หลัง Render deploy สำเร็จ เปิด `/health` ต้องเห็น `0.4.2.1` และหน้าเว็บควรขึ้น `Frontend v0.4.2.1 พร้อมใช้งาน`.

# Fooball v0.4.2 — Advanced Match Stats

เพิ่มจาก v0.4.1:
- ดึงและเก็บคอลัมน์ Shots / Shots on Target / Corners / Fouls / Yellow Cards / Red Cards จาก Football-Data เมื่อแหล่งข้อมูลมีให้
- หน้าเว็บแสดงการเปรียบเทียบค่าเฉลี่ยเจ้าบ้าน vs ทีมเยือน: ยิงทั้งหมด, ยิงตรงกรอบ, ความแม่นยำการยิง, conversion rate, เตะมุม, ฟาวล์, ใบเหลือง, ใบแดง
- ใช้บริบทเจ้าบ้าน/ทีมเยือน 18 นัดล่าสุด และยังคงใช้ Championship prior สำหรับทีมน้องใหม่ช่วงต้นฤดูกาล
- ไม่สร้างค่า possession หรือ shot-location ปลอม: แหล่งข้อมูลปัจจุบันไม่มีข้อมูลสองชนิดนี้แบบสม่ำเสมอย้อนหลัง
- Auto refresh, H2H score history และ prediction-vs-actual tracking จาก v0.4.1 ยังคงอยู่
- API /health และ frontend เป็น 0.4.2

Data roadmap:
- v0.4.2: result + shots + SOT + corners + fouls + cards จาก Football-Data
- v0.5: เพิ่ม provider/event-data สำหรับ possession, shot coordinates/zones, xG และประเภทประตู เมื่อเลือกแหล่งข้อมูลที่เสถียรและสิทธิ์ใช้งานเหมาะสม

Deploy:
1. Upload/replace all files in GitHub repository root.
2. Commit: `Upgrade Fooball v0.4.2 advanced stats`
3. Render Auto-Deploy from main.
4. ตรวจ `/health` ต้องได้ version `0.4.2`.

หมายเหตุ: prediction_history.json ยังเป็น local runtime storage บน Render Free และอาจหายหลัง redeploy/restart; production ควรย้ายไป PostgreSQL.

const $ = id => document.getElementById(id);
const pct = v => `${(Number(v) * 100).toFixed(1)}%`;
const FRONTEND_VERSION = '0.3.4';

function modelViewText(d){
  const values = [
    {name:d.home_team, value:d.home_win},
    {name:'เสมอ', value:d.draw},
    {name:d.away_team, value:d.away_win}
  ].sort((a,b)=>b.value-a.value);

  if(values[0].name === 'เสมอ'){
    return 'เกมมีแนวโน้มสูสี';
  }
  return `${values[0].name} ได้เปรียบ`;
}

async function init(){
  try{
    const r = await fetch('/api/teams', {cache:'no-store'});
    const data = await r.json();

    $('homeTeam').innerHTML='';
    $('awayTeam').innerHTML='';

    data.teams.forEach(t=>{
      $('homeTeam').add(new Option(t,t));
      $('awayTeam').add(new Option(t,t));
    });

    $('homeTeam').value='Arsenal';
    $('awayTeam').value='Coventry City';
  }catch(e){
    $('status').textContent='โหลดรายชื่อทีมไม่สำเร็จ';
  }
}

$('analyzeBtn').addEventListener('click', async()=>{
  const home = $('homeTeam').value;
  const away = $('awayTeam').value;

  if(home === away){
    $('status').textContent='กรุณาเลือกคนละทีม';
    return;
  }

  $('status').textContent='กำลังโหลดข้อมูลและคำนวณ…';
  $('analyzeBtn').disabled=true;

  try{
    const r = await fetch('/api/predict',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({home_team:home, away_team:away})
    });

    const d = await r.json();
    if(!r.ok) throw new Error(d.detail || 'เกิดข้อผิดพลาด');

    $('homeName').textContent = home;
    $('awayName').textContent = away;

    $('scorePick').textContent = d.most_likely_score;
    $('scoreProb').textContent = `โอกาส ${pct(d.most_likely_score_prob)}`;

    $('homeWin').textContent = pct(d.home_win);
    $('draw').textContent = pct(d.draw);
    $('awayWin').textContent = pct(d.away_win);

    $('homeBar').style.width = pct(d.home_win);
    $('drawBar').style.width = pct(d.draw);
    $('awayBar').style.width = pct(d.away_win);

    $('xg').textContent =
      `${Number(d.expected_home_goals).toFixed(2)} – ${Number(d.expected_away_goals).toFixed(2)}`;

    $('over25').textContent = pct(d.over_2_5);
    $('under25').textContent = pct(d.under_2_5);
    $('btts').textContent = pct(d.btts_yes);

    $('modelView').textContent = modelViewText(d);
    $('summaryLine').textContent =
      `โอกาสเจ้าบ้านชนะ ${pct(d.home_win)} · ประตูรวมคาดการณ์ ${Number(d.expected_total_goals).toFixed(2)} · สูง 2.5 ${pct(d.over_2_5)}`;

    $('topScores').innerHTML='';
    const scorelines = (d.top_scorelines && d.top_scorelines.length)
      ? d.top_scorelines
      : [{score:d.most_likely_score, probability:d.most_likely_score_prob}];

    scorelines.forEach((s, index)=>{
      const row = document.createElement('div');
      row.className = 'score-row';
      row.innerHTML = `
        <span class="score-rank">${index + 1}</span>
        <strong>${s.score}</strong>
        <span>${pct(s.probability)}</span>
      `;
      $('topScores').appendChild(row);
    });

    $('evidence').innerHTML='';
    (d.statistical_evidence || []).forEach(item=>{
      const box = document.createElement('div');
      box.className = 'evidence-item';
      const title = document.createElement('strong');
      title.textContent = item.title;
      const text = document.createElement('span');
      text.textContent = item.text;
      box.appendChild(title);
      box.appendChild(text);
      $('evidence').appendChild(box);
    });

    $('reasons').innerHTML='';
    (d.reasons || []).forEach(reason=>{
      const li = document.createElement('li');
      li.textContent = reason;
      $('reasons').appendChild(li);
    });

    $('modelNote').textContent =
      `โมเดล: Poisson + Dixon–Coles + Elo + prior สำหรับทีมน้องใหม่ · ไม่ใช้ราคาต่อรองเป็นตัวแปรหลัก`;

    $('results').classList.remove('hidden');
    $('status').textContent=`วิเคราะห์สำเร็จ · Frontend v${FRONTEND_VERSION}`;

    $('results').scrollIntoView({behavior:'smooth', block:'start'});

  }catch(e){
    $('status').textContent=`วิเคราะห์ไม่สำเร็จ: ${e.message}`;
  }finally{
    $('analyzeBtn').disabled=false;
  }
});

init();

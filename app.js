const $ = id => document.getElementById(id);
const pct = v => `${(Number(v)*100).toFixed(1)}%`;

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

  const home=$('homeTeam').value;
  const away=$('awayTeam').value;

  if(home===away){
    $('status').textContent='กรุณาเลือกคนละทีม';
    return;
  }

  $('status').textContent=
    'กำลังโหลดข้อมูลจริงและคำนวณ… ครั้งแรกอาจใช้เวลาสักครู่';

  $('analyzeBtn').disabled=true;

  try{

    const r=await fetch('/api/predict',{
      method:'POST',
      headers:{
        'Content-Type':'application/json'
      },
      body:JSON.stringify({
        home_team:home,
        away_team:away
      })
    });

    const d=await r.json();

    if(!r.ok){
      throw new Error(d.detail || 'เกิดข้อผิดพลาด');
    }

    $('homeName').textContent=home;
    $('awayName').textContent=away;

    $('scorePick').textContent=d.most_likely_score;
    $('scoreProb').textContent=
      `โอกาส ${pct(d.most_likely_score_prob)}`;

    $('homeWin').textContent=pct(d.home_win);
    $('draw').textContent=pct(d.draw);
    $('awayWin').textContent=pct(d.away_win);

    $('homeBar').style.width=pct(d.home_win);
    $('drawBar').style.width=pct(d.draw);
    $('awayBar').style.width=pct(d.away_win);

    $('xg').textContent=
      `${Number(d.expected_home_goals).toFixed(2)} – ` +
      `${Number(d.expected_away_goals).toFixed(2)}`;

    $('over25').textContent=pct(d.over_2_5);
    $('under25').textContent=pct(d.under_2_5);
    $('btts').textContent=pct(d.btts_yes);

    $('reasons').innerHTML='';

    (d.reasons || []).forEach(reason=>{
      const li=document.createElement('li');
      li.textContent=reason;
      $('reasons').appendChild(li);
    });

    $('modelNote').textContent=
      `${d.model} · ${d.data_source}`;

    $('results').classList.remove('hidden');

    $('status').textContent='วิเคราะห์สำเร็จ';

    $('results').scrollIntoView({
      behavior:'smooth',
      block:'start'
    });

  }catch(e){

    $('status').textContent=
      `วิเคราะห์ไม่สำเร็จ: ${e.message}`;

  }finally{

    $('analyzeBtn').disabled=false;

  }
});

init();

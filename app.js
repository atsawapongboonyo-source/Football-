const homeSelect = document.getElementById("homeTeam");
const awaySelect = document.getElementById("awayTeam");
const form = document.getElementById("predictionForm");
const resultSection = document.getElementById("results");

async function loadTeams() {
  try {
    const response = await fetch("/api/teams");

    if (!response.ok) {
      throw new Error("Unable to load teams");
    }

    const data = await response.json();
    const teams = data.teams || data;

    homeSelect.innerHTML =
      '<option value="">เลือกทีมเจ้าบ้าน</option>';

    awaySelect.innerHTML =
      '<option value="">เลือกทีมเยือน</option>';

    teams.forEach((team) => {
      const homeOption = document.createElement("option");
      homeOption.value = team;
      homeOption.textContent = team;

      const awayOption = document.createElement("option");
      awayOption.value = team;
      awayOption.textContent = team;

      homeSelect.appendChild(homeOption);
      awaySelect.appendChild(awayOption);
    });
  } catch (error) {
    console.error("Team loading error:", error);
  }
}

async function predictMatch(event) {
  event.preventDefault();

  const homeTeam = homeSelect.value;
  const awayTeam = awaySelect.value;

  if (!homeTeam || !awayTeam) {
    alert("กรุณาเลือกทั้งทีมเจ้าบ้านและทีมเยือน");
    return;
  }

  if (homeTeam === awayTeam) {
    alert("กรุณาเลือกทีมที่แตกต่างกัน");
    return;
  }

  try {
    const response = await fetch("/api/predict", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        home_team: homeTeam,
        away_team: awayTeam
      })
    });

    if (!response.ok) {
      throw new Error("Prediction failed");
    }

    const data = await response.json();

    console.log("Prediction:", data);

    if (resultSection) {
      resultSection.style.display = "block";
    }
  } catch (error) {
    console.error("Prediction error:", error);
    alert("ไม่สามารถวิเคราะห์การแข่งขันได้ในขณะนี้");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadTeams();

  if (form) {
    form.addEventListener("submit", predictMatch);
  }
});

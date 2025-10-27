async function send(){
  const el = document.getElementById("msg");
  const out = document.getElementById("out");
  const hotels = document.getElementById("hotels");
  const message = el.value.trim();
  if(!message) return;
  out.textContent = "Thinking…";
  hotels.innerHTML = "";
  try{
    const res = await fetch("/api/chat", {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({message})
    });
    const data = await res.json();
    out.textContent = data.reply || "(no reply)";
    if(data.best){
      const list = [data.best, ...(data.top || []).slice(1)];
      for(const h of list){
        const d = document.createElement("div");
        d.className = "hotel";
        d.innerHTML = `
          <div><strong>${h.name}</strong></div>
          <div>Total: ${h.total}</div>
          <div>Distance: ${h.distance}</div>
          <div>Dates: ${h.check_in} → ${h.check_out}</div>
          ${h.booking_url ? `<div><a href="${h.booking_url}" target="_blank" rel="noopener noreferrer">Book</a></div>` : ""}
        `;
        hotels.appendChild(d);
      }
    }
  }catch(e){
    out.textContent = "Error: " + e;
  }
}

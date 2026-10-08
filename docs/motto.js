/* Duvar yazısı bandı: .motto öğelerine günün cümlesini koyar, dokununca sıradakine geçer.
   Sayfa içeriği sonradan yeniden çizilirse window.mottoInit() çağrılır. */
(function(){
  var PH=["Kafanı işine, duygularını sevdiklerine ver","Zor zamanlarda da kazanacaksın","Kazanmayı sıradanlaştıracaksın","Kendine güven","Analizine güven",
    "Portföyünde her zaman nakit tut","Fırsatlar kaçmaz","Bekle ve izle","Tüm bilgiler fiyatlanmıştır","Sanane neden düşüyor neden yükseliyor",
    "Deniz sakin olduğunda dümeni herkes tutar","Gerektiğinde stop ol, portföyünü ve kazançlarını koru"];
  var d=new Date(),i=Math.floor((d-new Date(d.getFullYear(),0,0))/864e5)%PH.length;
  function all(){return document.querySelectorAll(".motto")}
  function paint(){all().forEach(function(m){var t=m.querySelector(".motto-t");if(t)t.textContent=PH[i]})}
  function next(){all().forEach(function(m){m.classList.add("fade")});
    setTimeout(function(){i=(i+1)%PH.length;paint();all().forEach(function(m){m.classList.remove("fade")})},220)}
  function init(){all().forEach(function(m){if(m.dataset.bound)return;m.dataset.bound="1";m.addEventListener("click",next);
    m.addEventListener("keydown",function(e){if(e.key==="Enter"||e.key===" "){e.preventDefault();next()}})});paint()}
  window.mottoInit=init;init();
})();

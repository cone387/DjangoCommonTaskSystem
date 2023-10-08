$(document).ready(function () {
  const $engineType = $('#id_engine_type');
  const $dockerConfig = $('.docker-config');
  const $processConfig = $('.process-config');

  function show_hide_fields(){
    const engineType = $engineType.find("option:selected").text();
    console.log("engineType is ", engineType);
    if(engineType === "Docker") {
        $dockerConfig.show();
        $processConfig.hide();
    }else if(engineType === "Process"){
        $dockerConfig.hide();
        $processConfig.show();
    }else{
        console.log("engineType is ", engineType);
    }
  }
  show_hide_fields();
  $engineType.on('change', show_hide_fields);
});
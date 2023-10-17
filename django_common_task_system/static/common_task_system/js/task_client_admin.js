$(document).ready(function () {
  const $programType = $('#id_program_type');
  const $dockerConfig = $('.docker-config');
  const $processConfig = $('.process-config');

  function show_hide_fields(){
    const programType = $programType.find("option:selected").text();
    console.log("programType is ", programType);
    if(programType === "Docker") {
        $dockerConfig.show();
        $processConfig.hide();
    }else if(programType === "Process"){
        $dockerConfig.hide();
        $processConfig.show();
    }else{
        console.log("programType is ", programType);
    }
  }
  show_hide_fields();
  $programType.on('change', show_hide_fields);
});
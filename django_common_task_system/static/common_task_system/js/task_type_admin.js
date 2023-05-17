$(document).ready(function () {
  const $taskParent = $('#id_parent');
  const $taskScriptField = $('.form-row.field-script');
  const $produceQueue = $('.fieldBox.field-queue');
  const $includeMeta = $('.fieldBox.field-include_meta');
  const $config = $('.form-row.field-config');
  const $taskScriptInput = $('#id_script');

  function show_hide_fields(){
    const parentTask = $taskParent.find("option:selected").text();
    console.log("parent task is ", parentTask);
    $config.hide();
    $taskScriptField.show();
    if(parentTask === "SQL执行") {
      $taskScriptInput.attr('placeholder', "请输入SQL语句, 多个语句用;分隔");
      $produceQueue.hide();
      $includeMeta.hide();
    }else if(parentTask === "SQL生产"){
      $taskScriptInput.attr('placeholder', "请输入单条select语句");
      $produceQueue.show();
      $includeMeta.show();
    }else if (parentTask === "Shell执行") {
        $produceQueue.hide();
        $taskScriptInput.attr('placeholder', "请输入shell命令，多个命令用;分隔");
    }else{
        $config.show();
        $taskScriptField.hide();
        $includeMeta.hide();
        $produceQueue.hide();
    }
  }
  show_hide_fields();
  $taskParent.on('change', show_hide_fields);
});
$(document).ready(function () {
  const $taskParent = $('#id_parent');
  const $taskScriptField = $('.form-row.field-script');
  const $produceQueue = $('.fieldBox.field-queue');
  const $includeMeta = $('.fieldBox.field-include_meta');
  const $config = $('.form-row.field-config');
  const $taskScriptInput = $('#id_script');
  const $executable = $('.form-row.field-executable_file');

  function show_hide_fields(){
    const parentTask = $taskParent.find("option:selected").text();
    console.log("parent task is ", parentTask);
    $config.hide();
    $taskScriptField.show();
    $executable.hide();
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
    }else if(parentTask === "自定义可执行任务"){
        $executable.show();
        $produceQueue.hide();
        $includeMeta.hide();
        $taskScriptField.hide();
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
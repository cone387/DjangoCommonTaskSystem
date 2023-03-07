$(document).ready(function () {
  const $scheduleType = $('#id_schedule_type');
  const $crontab = $('.form-row.field-crontab');
  const $onceSchedule = $('.form-row.field-once_schedule')
  const $periodSchedule = $('.form-row.field-period_schedule');

  const $timingDiv = $("div[class*='timing']");
  const $timingType = $('#id_timing_type');
  const $timingDay = $('.form-row.field-timing_time,.fieldBox.field-timing_period');
  const $timingWeekday = $('.form-row.field-timing_weekday');
  const $timingMonthday = $('.form-row.field-timing_monthday');
   const $timingYear = $('.form-row.field-timing_year');
  const $timingDatetime = $('.form-row.field-timing_datetime');


  function show_hide_timing_fields(){
    const timingType = $timingType.val();
    console.log("timingType is ", timingType);
    if(timingType === "DATETIME"){
      $timingWeekday.hide();
      $timingDay.hide();
      $timingMonthday.hide();
      $timingYear.hide();
      $timingDatetime.show();
      return;
    }
    $timingDatetime.hide();
    $timingDay.show();
    const $timingPeriodUnit = $('#id_period_unit');
    if(timingType === 'DAY'){
      $timingWeekday.hide();
      $timingMonthday.hide();
      $timingYear.hide();
      $timingPeriodUnit.text('天');
    }
    if(timingType === 'WEEKDAY'){
      $timingWeekday.show();
      $timingMonthday.hide();
      $timingYear.hide();
      $timingPeriodUnit.text('周');
    }else if(timingType === "MONTHDAY"){
      $timingWeekday.hide();
      $timingMonthday.show();
      $timingYear.hide();
      $timingPeriodUnit.text('月');
    }else if(timingType === "YEAR"){
      $timingWeekday.hide();
      $timingMonthday.hide();
      $timingYear.show();
      $timingPeriodUnit.text('年');
    }
  }

  function show_hide_timing(show){
    if(show){
      $timingDiv.show();
      show_hide_timing_fields();
    }else{
      $timingDiv.hide();
    }
  }

  function show_hide_fields() {
    console.log($scheduleType.val());
    const scheduleType = $scheduleType.val();
    if (scheduleType === 'C') {
      $crontab.show();
      $onceSchedule.hide();
      $periodSchedule.hide();
    } else if (scheduleType === 'S') {
      $crontab.hide();
      $onceSchedule.hide();
      $periodSchedule.show();
    } else if (scheduleType === 'O') {
      $crontab.hide();
      $onceSchedule.show();
      $periodSchedule.hide();
    }else if(scheduleType === 'T'){
      $crontab.hide();
      $onceSchedule.hide();
      $periodSchedule.hide();
    }else if(scheduleType === 'N'){
      $crontab.hide();
      $onceSchedule.hide();
      $periodSchedule.hide();
    }
    show_hide_timing(scheduleType === 'T');
  }
  show_hide_fields();
  $scheduleType.on('change', show_hide_fields);
  $timingType.on('change', show_hide_timing_fields);
});
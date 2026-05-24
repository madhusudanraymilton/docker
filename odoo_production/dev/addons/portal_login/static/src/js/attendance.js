// odoo.define('portal_attendance_popup', function (require) {
//     'use strict';
//     const ajax = require('web.ajax');

//     document.addEventListener("DOMContentLoaded", function() {

//         function openModal(op){
//             ajax.jsonRpc("/portal/attendance/modal/" + op, 'call', {})
//             .then(function(html){
//                 const container = document.getElementById("attendance_modal_container");
//                 container.innerHTML = html;

//                 const modal = container.querySelector("#attendance_modal");
//                 const saveBtn = modal.querySelector("#modal_save");
//                 const closeBtn = modal.querySelector("#modal_close");

//                 saveBtn.onclick = function(){
//                     const date = modal.querySelector('input[name="date"]').value;
//                     const time = modal.querySelector('input[name="time"]').value;

//                     ajax.jsonRpc("/portal/attendance/save", 'call', {
//                         date: date,
//                         time: time,
//                         operation: op
//                     }).then(function(res){
//                         alert(res.message);
//                         container.innerHTML = '';
//                         location.reload();
//                     });
//                 }

//                 closeBtn.onclick = function(){
//                     container.innerHTML = '';
//                 }
//             });
//         }

//         document.getElementById("btn_check_in").onclick = function(){ openModal('check_in'); }
//         document.getElementById("btn_check_out").onclick = function(){ openModal('check_out'); }
//     });
// });

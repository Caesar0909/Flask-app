
// Unpack data by key
function unpack(rows, key) { return rows.map(function(row) {return row[key]; });};

// Takes an array of options and the select selector
function setSelectOptions(options, selector) {
    for (var i=0; i < options.length; i++) {
        var newOption = document.createElement('option');

        newOption.text = options[i];
        selector.appendChild(newOption);
    }
};

// Plotly Loading Bars
function plotlyLoadingBars(id) {
    var text = "<div class='plotlybars-wrapper'>\
                    <div class='plotlybars'>\
                        <div class='plotlybars-bar b1'></div>\
                        <div class='plotlybars-bar b2'></div>\
                        <div class='plotlybars-bar b3'></div>\
                        <div class='plotlybars-bar b4'></div>\
                        <div class='plotlybars-bar b5'></div>\
                        <div class='plotlybars-bar b6'></div>\
                        <div class='plotlybars-bar b7'></div>\
                    </div>\
                    <div class='plotlybars-text'>\
                        loading...\
                    </div>\
                </div>";

    document.getElementById(id).innerHTML = text;
};

// Make a table searcheable
function searchTable(id) {
    var $_rows = $('table#' + id + ' tbody tr');

    $('input#' + id).keyup(function() {
        var $_val = '^(?=.*\\b' + $.trim($(this).val()).split(/\s+/).join('\\b)(?=.*\\b') + ').*$';
        var $_reg = RegExp($_val, 'i');
        var $_text;

        $_rows.show().filter(function(){
            $_text = $(this).text().replace(/\s+/g, ' ');
            return !$_reg.test($_text);
        }).hide();
    });
};

// Download data from modal
function downloadData(){

    //var sn = $('form p#form-sn');
    var sn = document.getElementById('form-sn').getAttribute('data-sn');
    var start = document.getElementById('form-start-date').value;
    var end = document.getElementById('form-end-date').value;

    if (start >= end){
        var msg = "<div class='form-control-feedback'>Sorry, the start date must precede the end date.</div>";

        $('#form-start-date').parent().closest('.row').addClass(' has-danger');
    }
    else {
        // Split datetimes to correct format
        start = start.split('/');
        start = start[2] + '-' + start[0] + '-' + start[1];

        end = end.split('/');
        end = end[2] + '-' + end[0] + '-' + end[1];

        // Build the uri
        var uri = window.location.protocol + '//' + document.domain + ':' +
                    location.port + '/api/v1.0/data/csv/' + sn +
                    '/' + start + '/' + end;

        window.location.href = uri;

        // Close the modal
        $('.modal').modal('hide');
    }
};

/*
var table = function(d){
	var tbody = $("#data-table-body");

	$.each(d, function(key, value){
		// Create a row with tds inside of it
		var tr = "<tr><td>" + value.timestamp + "</td><td>" + (value.conc_rt * 1000).toFixed(1) + "</td>";
		tr += "<td>" + (value.conc_hr * 1000).toFixed(1) + "</td><td>" + value.flowrate + "</td><td>" + value.windspeed + "</td>";
		tr += "<td>" + value.winddir + "</td><td>" + value.ambient_temp + "</td><td>" + value.flag + "</td></tr>";

		tbody.append(tr);
	})
}
*/

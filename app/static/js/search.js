$(document).ready(function() {
    // Page setup
    var attributeChart = $(".details-attribute-chart");
    var currentGameVector;
    var detailsExpanded = false;
    var detailsRadarChart;
    var selectedAppID;
    var unselected = [];

    if (userAccount != "None") {
        $(".user-menu").fadeIn(150).css("display", "inline-block");
        $('#user-vector-toggle').bootstrapToggle({
            on: 'Yes',
            off: 'No'
        });
        $('#user-vector-toggle').bootstrapToggle(vector_toggle);
    }
    else
        $(".user-login").fadeIn(150).css("display", "inline-block");

    if (currentGameTitle !== undefined) {
        $('html, body').animate({
            scrollTop: $(".global-search").offset().top - 15
        }, 400);

        console.log(currentGameFeatureNames);

        var queryString = window.location.search;
        queryString = queryString.substring(1);

        var parseQueryString = function( queryString ) {
            var params = {}, queries, temp, i, l;
            // Split into key/value pairs
            queries = queryString.split("&");
            // Convert the array of strings into an object
            for ( i = 0, l = queries.length; i < l; i++ ) {
                temp = queries[i].split('=');
                params[temp[0]] = decodeURI(temp[1]);
            }
            return params;
        };
        var parsed = parseQueryString(queryString);
        if ('removed_features' in parsed) {
            unselected = atob(parseQueryString(queryString)['removed_features']).split(',');
            console.log(unselected);
        } else {
            unselected = null;
        }

        var tags_div = $(".tags");
		var search_tags = tags_div.data("tags");
		for (var key in search_tags) {
            if (!search_tags.hasOwnProperty(key)) continue;
            var value = search_tags[key];
            if (unselected !== null && unselected.indexOf(value) !== -1){
                tags_div.append("<p class='tag'>" + value + "</p>")
            } else {
                tags_div.append("<p class='tag selected'>" + value + "</p>")
            }
		}
        tags_div.append("<button type='submit' class='btn btn-desc' style='display: block; margin: 0 auto;'>Remove/Add Features</button>")

    }

    if (toggle_modal !== undefined) {
        $("#login-modal").modal();
        $('.login-input').focus();
    }

    if (vector_toggle == "on") {
        $('.no-vector-ranking').css("display", "none");
        $('.vector-ranking').css("display", "block");
    }

    // Handle event listeners

    // Thanks to: http://stackoverflow.com/questions/28631219/how-can-i-unfocus-the-modal-trigger-button-after-closing-the-modal-in-bootstrap
    $("#login-modal").on("shown.bs.modal", function(e) {
        $('.user-login').one('focus', function(e) {
            $(this).blur();
        });
        $('.login-input').focus();
    });

    $(".details-close").click(function() {
        $(".details-content-wrapper").fadeOut(150, function() {
            $(".details-overlay").animate({
                width: '0px'
            }, 300);
            detailsExpanded = false;
        });
    });

    $(".details-query").click(function() {
        var user_vector = "";
        if ($('#user-vector-toggle').prop('checked'))
            user_vector = "&user_vector=on";

        window.location.replace("/?app_id=" + selectedAppID + user_vector);
    });

    $(".logout").click(function() {
        document.cookie = 'username=;expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        document.cookie = 'library_vector=;expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        document.cookie = 'steam_ID=;expires=Thu, 01 Jan 1970 00:00:01 GMT;';
        location.reload();
    });

    $(".result-box").click(function() {
        var resultBox = $(this);
        var updateDetails = function() {
            var gameTitle = resultBox.data("title");
            $(".details-title").text(gameTitle);
            $(".details-img").attr("src", resultBox.children(".result-img").attr("src"));
            $(".details-link").attr("href", resultBox.data("steam-url"));

            var tagsDiv = $(".details-tags");
            tagsDiv.empty();
            $.each(JSON.parse(atob(resultBox.data("tags"))), function(index, tag) {
                tagsDiv.append("<p class='tag unselectable'>" + tag + "</p>");
            });
            selectedAppID = resultBox.data("app-id");

            var gameVector = resultBox.data("features").map(Math.log);
            var data = {
                labels: currentGameFeatureNames,
                datasets: [{
                    label: gameTitle,
                    backgroundColor: "rgba(255,99,132,0.2)",
                    borderColor: "rgba(255,99,132,1)",
                    pointBackgroundColor: "rgba(255,99,132,1)",
                    pointBorderColor: "#fff",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(255,99,132,1)",
                    data: gameVector
                }, {
                    label: currentGameTitle,
                    backgroundColor: "rgba(90, 179, 206, 0.2)",
                    borderColor: "rgba(90, 179, 206, 1)",
                    pointBackgroundColor: "rgba(90, 179, 206, 1)",
                    pointBorderColor: "#fff",
                    pointHoverBackgroundColor: "#fff",
                    pointHoverBorderColor: "rgba(90, 179, 206, 1)",
                    data: currentGameFeatures
                }]
            };

            if (detailsRadarChart !== undefined)
                detailsRadarChart.destroy();

            detailsRadarChart = new Chart(attributeChart, {
                type: 'radar',
                data: data,
                options: {
                    legend: {
                        position: 'bottom'
                    },
                    scale: {
                        ticks: {
                            display: false
                        }
                    },
                    tooltips: {
                        enabled: false
                    }
                }
            });

            $(".details-overlay").animate({
                width: '400px'
            }, 300, function() {
                $(".details-content-wrapper").fadeIn(150);
                detailsExpanded = true;
            });
        };

        if (detailsExpanded) {
            var detailsBody = $(".details-body");
            detailsBody.fadeOut(200, function() {
                updateDetails();
                detailsBody.fadeIn(200);
            });
        } else
            updateDetails();
    });

    $(".tag").click(function() {
        var tag = $(this);
        if (tag.hasClass("selected"))
            $(this).removeClass("selected");
        else
            $(this).addClass("selected");
    });

    $(".btn-desc").click(function() {
        var p_list = document.querySelectorAll("p.tag");
        var array = [];
        for(var i = 0; i < p_list.length; i++) {
        // Only if there is only single class
            if(p_list[i].className == 'tag') {
                // Do something with the element e[i]
                array.push(p_list[i].innerHTML);
            }
        }
        console.log(array);

        var user_vector = "";
        if ($('#user-vector-toggle').prop('checked'))
            user_vector = "&user_vector=on";

        var removed_features = "";
        if (array.length !== 0){
            removed_features = "&removed_features=" + btoa(array.join(","));
        }
        window.location.replace("/?app_id=" + currentAppID + user_vector + removed_features);
    });

    $('#user-vector-toggle').change(function() {
        if($(this).prop('checked')) {
            $('.no-vector-ranking').fadeOut(150, function() {
                $('.vector-ranking').fadeIn(150);
            });
        }
        else {
            $('.vector-ranking').fadeOut(150, function() {
                $('.no-vector-ranking').fadeIn(150);
            });
        }
    })
});

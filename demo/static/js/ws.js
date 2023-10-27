$(function () {                                                                                      
    let ws_path = $('#ws_path').val()
    let host = window.location.host + ws_path
    let protocal = window.location.protocol == 'https:' ? 'wss' : 'ws'
    let ws = new window.WebSocket(protocal + '://' + host)
                          
    ws.onopen = function () {
        $("#chat-circle").click()
    }
    ws.onmessage = function (evt) {
        let data = evt.data
        generate_message(data, 'user');
    }
    ws.onclose = function (e) {
        console.log('err', e)
        $("#chat-circle").click()
    }
    ws.onerror = function (ev) {
        
    }

    var INDEX = 0;
    $("#chat-submit").click(function (e) {
        e.preventDefault();
        var msg = $("#chat-input").val();
        if (msg.trim() == '') {
            return false;
        }
        setTimeout(function () {
            generate_message(msg, 'self');
            setTimeout(() => {
                ws.send(JSON.stringify({
                    'to_user': $('#input-user').val(),
                    'msg': msg,
                }))
            }, 0)
        }, 0)

    })
    function generate_message(msg, type) {
        INDEX++;
        img = '1'
        if (type == 'user') img = '2'
        var str = "";
        str += "<div id='cm-msg-" + INDEX + "' class=\"chat-msg " + type + "\">";
        str += "          <span class=\"msg-avatar\">";
        str += "            <img src=\"\/static\/imgs\/" + img + ".jpg.png\">";
        str += "          <\/span>";
        str += "          <div class=\"cm-msg-text\">";
        str += msg;
        str += "          <\/div>";
        str += "        <\/div>";
        $(".chat-logs").append(str);
        $("#cm-msg-" + INDEX).hide().fadeIn(300);
        if (type == 'self') {
            $("#chat-input").val('');
        }
        $(".chat-logs").stop().animate({ scrollTop: $(".chat-logs")[0].scrollHeight }, 1000);
    }

    $(document).delegate(".chat-btn", "click", function () {
        var value = $(this).attr("chat-value");
        var name = $(this).html();
        $("#chat-input").attr("disabled", false);
        generate_message(name, 'self');
    })

    $("#chat-circle").click(function () {
        $("#chat-circle").toggle('scale');
        $(".chat-box").toggle('scale');
    })

    $(".chat-box-toggle").click(function () {
        $("#chat-circle").toggle('scale');
        $(".chat-box").toggle('scale');
    })

})
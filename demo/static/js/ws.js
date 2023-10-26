(function (window) {
    let host = document.querySelector('#ws_host').getAttribute('value')
    let protocal = window.location.protocol == 'https:' ? 'wss': 'ws'
    let ws = new window.WebSocket(protocal + '://' + host)
    let msg_container = document.querySelector('#receive_msg')
    ws.onopen = function () {
        ws.send('send data ... ')
    }
    ws.onmessage = function (evt) {
        let data = evt.data
        let msg_item = document.createElement('li')
        msg_item.innerHTML = data
        msg_container.appendChild(msg_item)
        console.log('receive data', data)
    }
    ws.onclose = function () {
        console.log('ws closed')
        document.querySelector('#msg').setAttribute('placeholder', '连接断开')
    }
    ws.onerror = function (ev) {
        console.log(ev)
    }
    
    document.querySelector('#send_msg').addEventListener('click', () => {
        let to_user = document.querySelector('#to_user').value
        let msg = document.querySelector('#msg').value
        console.log({'to_user': to_user, 'msg': msg})
        if (ws.readyState == ws.CLOSING || ws.readyState == ws.CLOSED) {
            document.querySelector('#msg').setAttribute('placeholder', '消息发送失败，因为与无法连接服务器')
        } else {
            ws.send(JSON.stringify({
                'msg': msg,
                'to_user': to_user
            }))
            document.querySelector('#msg').value = ''
            document.querySelector('#msg').setAttribute('placeholder', '发送成功')
        }
        setTimeout(() => {
            document.querySelector('#msg').setAttribute('placeholder', '请输入')
        }, 500)
    })
})(window)
(function (window) {
    let host = document.querySelector('#ws_host').getAttribute('value')
    console.log(host)
    let ws = new window.WebSocket('ws://' + host)
    let msg_container = document.querySelector('#receive_msg')
    ws.onopen = function () {
        ws.send('send data ... ')
        let i = 0
        let timer = setInterval(() => {
            ws.send('hello hahah > ' + i)
            i++
            if (i >= 3) {
                clearInterval(timer)
                setTimeout(() => ws.close(), 0)
            }
        }, 1000)
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
    }
    ws.onclose = function (e) {
        console.log('err', e)
    }
    ws.onerror = function (ev) { }
})(window)
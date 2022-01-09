from blinker import signal, Signal



setup: Signal= signal('di.setup')
boot: Signal= signal('di.boot')
init: Signal = signal('di.init')
ready: Signal = signal('di.ready')
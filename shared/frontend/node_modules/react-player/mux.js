
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/Mux').default
      module.exports = createReactPlayer([{
        key: 'mux',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    
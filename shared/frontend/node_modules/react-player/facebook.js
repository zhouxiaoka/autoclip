
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/Facebook').default
      module.exports = createReactPlayer([{
        key: 'facebook',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    
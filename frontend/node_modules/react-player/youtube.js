
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/YouTube').default
      module.exports = createReactPlayer([{
        key: 'youtube',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    
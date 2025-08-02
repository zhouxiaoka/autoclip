
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/FilePlayer').default
      module.exports = createReactPlayer([{
        key: 'file',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    
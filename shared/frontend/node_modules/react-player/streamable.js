
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/Streamable').default
      module.exports = createReactPlayer([{
        key: 'streamable',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    
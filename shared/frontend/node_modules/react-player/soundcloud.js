
      var createReactPlayer = require('./lib/ReactPlayer').createReactPlayer
      var Player = require('./lib/players/SoundCloud').default
      module.exports = createReactPlayer([{
        key: 'soundcloud',
        canPlay: Player.canPlay,
        lazyPlayer: Player
      }])
    
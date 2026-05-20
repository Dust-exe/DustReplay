using System.Windows;
using System.Windows.Controls;

namespace DustReplay.App.Controls;

public partial class MenuRow : UserControl
{
    public static readonly DependencyProperty TitleProperty =
        DependencyProperty.Register(nameof(Title), typeof(string), typeof(MenuRow),
            new PropertyMetadata("", (d, e) => ((MenuRow)d).TitleText.Text = (string)e.NewValue));

    public static readonly DependencyProperty SubtitleProperty =
        DependencyProperty.Register(nameof(Subtitle), typeof(string), typeof(MenuRow),
            new PropertyMetadata("", (d, e) => ((MenuRow)d).SubText.Text = (string)e.NewValue));

    public static readonly DependencyProperty IconGlyphProperty =
        DependencyProperty.Register(nameof(IconGlyph), typeof(string), typeof(MenuRow),
            new PropertyMetadata("\uE8B7", (d, e) => ((MenuRow)d).IconText.Text = (string)e.NewValue));

    public string Title { get => (string)GetValue(TitleProperty); set => SetValue(TitleProperty, value); }
    public string Subtitle { get => (string)GetValue(SubtitleProperty); set => SetValue(SubtitleProperty, value); }
    public string IconGlyph { get => (string)GetValue(IconGlyphProperty); set => SetValue(IconGlyphProperty, value); }

    public event RoutedEventHandler? Click;

    public MenuRow() => InitializeComponent();

    private void RowBtn_Click(object sender, RoutedEventArgs e) => Click?.Invoke(this, e);
}
